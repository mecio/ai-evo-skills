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
    schema = json.loads(files('ai_evo_skills').joinpath('execution-plan.schema.json').read_text(encoding='utf-8'))
    errors = list(Draft202012Validator(schema).iter_errors(step))
    if errors:
        details = '\n'.join(f"- {'.'.join(map(str, error.absolute_path)) or 'plan'}: {error.message}" for error in errors)
        raise ExecutionError('invalid execution plan; resolve all step output references before execution:\n' + details)
    app, session = step['application'], step['application']['session']
    permitted = session['reuse'] != 'never'
    supported = bool(session['resume_arguments'])
    if (session['resume_permitted'] != permitted or session['resume_supported'] != supported
            or session['resume_allowed'] != (permitted and supported)
            or session['corrections_only'] != (session['reuse'] == 'correction-only')):
        raise ExecutionError('inconsistent session capability or reuse policy')
    if app['profile']['adapter'] != app['executor']:
        raise ExecutionError('profile adapter must match the execution adapter')
    recipe = 'resolved' if 'uses' in step else 'not-applicable'
    if step['handoff']['planning']['recipe'] != recipe:
        raise ExecutionError('handoff planning status does not match the plan kind')


def run_delegated(argv: list[str], *, cwd: str, env: dict[str, str], prompt: str | None, timeout: float) -> int:
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
        deadline = time.monotonic() + timeout
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
            text=True, start_new_session=True,
        )
        pending = prompt
        while True:
            if cancelled:
                tree.stop(process)
                return 128 + cancelled
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ExecutionTimeout(f'delegated command timed out after {timeout:g} seconds; process tree terminated')
            try:
                process.communicate(input=pending, timeout=min(remaining, 0.2))
                if cancelled:
                    tree.stop(process)
                    return 128 + cancelled
                status = process.returncode if process.returncode >= 0 else 128 - process.returncode
                tree.stop(process)
                return 128 + cancelled if cancelled else status
            except subprocess.TimeoutExpired:
                pending = None
    except BaseException:
        if process is not None:
            tree.stop(process)
        raise
    finally:
        try:
            if tree is not None:
                tree.close()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
