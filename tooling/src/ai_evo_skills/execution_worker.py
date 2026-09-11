"""Private supervisor entry point; its only child tree belongs to one step."""
import json
import os
import sys

from .execution import ExecutionTimeout, _run_supervised


def main(result_fd: int, gate_fd: int) -> None:
    # Do not leak the result channel to the delegate or its descendants.
    os.set_inheritable(result_fd, False)
    os.set_inheritable(gate_fd, False)
    with os.fdopen(result_fd, 'w', encoding='utf-8') as channel:
        def ready():
            channel.write('R')
            channel.flush()
            try:
                if os.read(gate_fd, 1) != b'G':
                    raise RuntimeError('supervisor startup cancelled')
            finally:
                os.close(gate_fd)

        try:
            arguments = json.load(sys.stdin)
            status = _run_supervised(**arguments, on_ready=ready)
            result = {'kind': 'exit', 'status': status}
        except ExecutionTimeout as exc:
            result = {'kind': 'timeout', 'message': str(exc)}
        except Exception as exc:
            # The parent reads after exit: keep the result below pipe capacity,
            # even for multibyte diagnostics, so reporting cannot block cleanup.
            result = {'kind': 'error', 'message': str(exc)[:500]}
        json.dump(result, channel, ensure_ascii=False)
