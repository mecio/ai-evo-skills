"""Validation of resolved execution snapshots, independent of the project catalog."""
from __future__ import annotations

from importlib.resources import files
import json
from typing import Any

from jsonschema import Draft202012Validator

from .process_tree import ProcessTree


class ExecutionError(ValueError):
    pass


class ExecutionTimeout(ExecutionError):
    pass


def validate_plan(step: Any) -> None:
    if isinstance(step, dict) and 'when' in step:
        raise ExecutionError('when must be resolved by recipe advance before command execute')
    schema = json.loads(files('ai_evo_skills').joinpath('execution-plan.schema.json').read_text(encoding='utf-8'))
    errors = list(Draft202012Validator(schema).iter_errors(step))
    if errors:
        details = '\n'.join(f"- {'.'.join(map(str, error.absolute_path)) or 'plan'}: {error.message}" for error in errors)
        raise ExecutionError('invalid execution plan; resolve all step output references before execution:\n' + details)
    validate_step_consistency(step)


def validate_step_consistency(step: dict[str, Any]) -> None:
    """Semantic checks shared by executable and not-yet-resolved recipe steps."""
    app, session = step['application'], step['application']['session']
    permitted = session['reuse'] != 'never'
    supported = bool(session['resume_arguments'])
    if (session['resume_permitted'] != permitted or session['resume_supported'] != supported
            or session['resume_allowed'] != (permitted and supported)
            or session['corrections_only'] != (session['reuse'] == 'correction-only')):
        raise ExecutionError('inconsistent session capability or reuse policy')
    if app['profile']['adapter'] != app['executor']:
        raise ExecutionError('profile adapter must match the execution adapter')
    if 'output_contract' in app:
        from .output_contract import check_schema
        check_schema(app['output_contract']['schema'])
        if app['output_contract']['format'] != 'json-' + app['output_contract']['schema']['type']:
            raise ExecutionError('output contract format must match schema root type')
    recipe = 'resolved' if 'uses' in step else 'not-applicable'
    if step['handoff']['planning']['recipe'] != recipe:
        raise ExecutionError('handoff planning status does not match the plan kind')


class _InputPump:
    """Deliver every byte without blocking deadline and signal handling."""

    def __init__(self, stream, value: str):
        import os
        self.stream = stream
        self.data = memoryview(value.encode('utf-8'))
        self.offset = 0
        os.set_blocking(stream.fileno(), False)

    def advance(self):
        import os
        if self.stream.closed:
            return
        try:
            if self.offset < len(self.data):
                self.offset += os.write(self.stream.fileno(), self.data[self.offset:self.offset + 65536])
            if self.offset == len(self.data):
                self.stream.close()
        except BlockingIOError:
            pass
        except BrokenPipeError:
            self.stream.close()


def run_delegated(argv: list[str], *, cwd: str, env: dict[str, str], prompt: str | None, timeout: float,
                  stdout=None, stderr=None) -> int:
    """Run supervision in an isolated process, never adopting the caller's orphans."""
    import os
    from pathlib import Path
    import select
    import signal
    import subprocess
    import sys
    import time

    deadline = time.monotonic() + timeout
    cancelled = 0

    def cancel(signum, _frame):
        nonlocal cancelled
        cancelled = signum

    previous = {sig: signal.signal(sig, cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
    reader, writer = os.pipe()
    gate_reader, gate_writer = os.pipe()
    worker = None
    authorized = False
    try:
        worker = subprocess.Popen(
            [sys.executable, '-c',
             'import sys; sys.path.insert(0, sys.argv[1]); '
             'from ai_evo_skills.execution_worker import main; main(int(sys.argv[2]), int(sys.argv[3]))',
             str(Path(__file__).resolve().parent.parent), str(writer), str(gate_reader)],
            stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
            pass_fds=(writer, gate_reader), start_new_session=True,
        )
        os.close(writer)
        writer = None
        os.close(gate_reader)
        gate_reader = None
        pump = _InputPump(worker.stdin, json.dumps(dict(
            argv=argv, cwd=cwd, env=env, prompt=prompt, timeout=timeout, deadline=deadline)))
        handshake = None
        forwarded = False
        while worker.poll() is None:
            # Until the gate is granted the worker cannot create a native child.
            # It is safe to kill even a worker stuck in interpreter startup.
            if not authorized and (cancelled or time.monotonic() >= deadline):
                worker.kill()
                worker.wait()
                if cancelled:
                    return 128 + cancelled
                raise ExecutionTimeout(f'delegated command timed out after {timeout:g} seconds during supervisor startup')
            pump.advance()
            if handshake is None and select.select([reader], [], [], 0)[0]:
                handshake = os.read(reader, 1)
                if handshake == b'R':
                    os.write(gate_writer, b'G')
                    authorized = True
                    os.close(gate_writer)
                    gate_writer = None
            if authorized and cancelled and not forwarded and worker.poll() is None:
                worker.send_signal(cancelled)
                forwarded = True
            time.sleep(0.01)
        with os.fdopen(reader, 'r', encoding='utf-8') as channel:
            reader = None
            payload = ((handshake or b'').decode('utf-8') + channel.read()).removeprefix('R')
        if cancelled:
            return 128 + cancelled
        if not payload:
            raise ExecutionError(f'delegated supervisor exited without a result (status {worker.returncode})')
        result = json.loads(payload)
        if result['kind'] == 'timeout':
            raise ExecutionTimeout(result['message'])
        if result['kind'] == 'error':
            raise ExecutionError(result['message'])
        return result['status']
    finally:
        if worker is not None:
            if worker.poll() is None:
                worker.terminate() if authorized else worker.kill()
                worker.wait()
            if worker.stdin is not None:
                worker.stdin.close()
        for fd in (reader, writer, gate_reader, gate_writer):
            if fd is not None:
                os.close(fd)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _run_supervised(argv: list[str], *, cwd: str, env: dict[str, str], prompt: str | None,
                    timeout: float, on_ready, deadline: float | None = None) -> int:
    """Bound execution and reap all step descendants, including new process sessions."""
    import signal
    import subprocess
    import time

    cancelled = 0

    def cancel(signum, _frame):
        nonlocal cancelled
        cancelled = signum

    previous = {sig: signal.signal(sig, cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
    process = None
    tree = None
    try:
        tree = ProcessTree()
        if deadline is None:
            deadline = time.monotonic() + timeout
        on_ready()
        if cancelled:
            return 128 + cancelled
        if time.monotonic() >= deadline:
            raise ExecutionTimeout(f'delegated command timed out after {timeout:g} seconds during supervisor startup')
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
            start_new_session=True,
        )
        pump = _InputPump(process.stdin, prompt) if prompt is not None else None
        while True:
            if cancelled:
                tree.stop(process)
                return 128 + cancelled
            if time.monotonic() >= deadline:
                raise ExecutionTimeout(f'delegated command timed out after {timeout:g} seconds; process tree terminated')
            if pump is not None:
                pump.advance()
            if process.poll() is not None:
                status = process.returncode if process.returncode >= 0 else 128 - process.returncode
                tree.stop(process)
                return 128 + cancelled if cancelled else status
            time.sleep(0.01)
    except BaseException:
        if process is not None:
            tree.stop(process)
        raise
    finally:
        try:
            if process is not None and process.stdin is not None:
                process.stdin.close()
            if tree is not None:
                tree.close()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
