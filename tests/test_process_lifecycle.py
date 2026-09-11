import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

import test_cli as fixtures


class ProcessLifecycleTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_timeout_reaps_process_with_non_utf8_name(self):
        from ai_evo_skills.execution import ExecutionTimeout, run_delegated
        temporary, root = self.repository()
        with temporary:
            marker = root / 'named.pid'
            child = (
                "import ctypes,os,signal,time; from pathlib import Path; "
                "assert ctypes.CDLL(None).prctl(15, b'bad) \\xff\\nname', 0, 0, 0) == 0; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "Path('named.pid').write_text(str(os.getpid())); time.sleep(60)"
            )
            try:
                with self.assertRaises(ExecutionTimeout):
                    run_delegated([sys.executable, '-c', child], cwd=str(root),
                                  env=os.environ.copy(), prompt=None, timeout=1)
                self.assertTrue(marker.exists(), 'probe must start before the timeout')
                pid = int(marker.read_text())
                self.assertFalse(Path(f'/proc/{pid}').exists(), 'process must be terminated and reaped')
            finally:
                if marker.exists():
                    pid = int(marker.read_text())
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        os.waitpid(pid, 0)
                    except ChildProcessError:
                        pass

    def test_timeout_and_termination_kill_descendants_even_when_the_leader_exits(self):
        for interrupt in (False, True):
            with self.subTest(interrupt=interrupt):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, 'codex')
                    self.add_command(root)
                    plan = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
                    self.assertEqual(0, plan.returncode, plan.stderr)
                    step = json.loads(plan.stdout)
                    grandchild = "import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path('grandchild.pid').write_text(str(os.getpid())); time.sleep(60)"
                    leader = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1]]); time.sleep(60)"
                    step['application']['command'] = [sys.executable, '-c', leader, grandchild]
                    proc = subprocess.Popen(
                        fixtures.COMMAND + ['command', 'execute', '--timeout', '20' if interrupt else '1'],
                        cwd=root, env=fixtures.CLI_ENV, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    )
                    proc.stdin.write(json.dumps(step))
                    proc.stdin.close()
                    proc.stdin = None
                    deadline = time.monotonic() + 5
                    try:
                        while not (root / 'grandchild.pid').exists() and time.monotonic() < deadline:
                            time.sleep(0.02)
                        self.assertTrue((root / 'grandchild.pid').exists())
                        pid = int((root / 'grandchild.pid').read_text())
                        if interrupt:
                            proc.send_signal(signal.SIGTERM)
                        stdout, stderr = proc.communicate(timeout=5)
                        self.assertEqual(143 if interrupt else 124, proc.returncode, stderr)
                        if not interrupt:
                            self.assertIn('timed out', stderr)
                        # A reparented child can briefly remain a zombie; it must not be running.
                        status = Path(f'/proc/{pid}/status')
                        if status.exists():
                            self.assertIn('State:\tZ', status.read_text())
                    finally:
                        if proc.poll() is None:
                            proc.terminate()
                            proc.communicate(timeout=5)

    def test_orphaned_descendants_in_new_sessions_are_reaped(self):
        for ending in ('timeout', 'SIGTERM', 'SIGINT', 'normal'):
            with self.subTest(ending=ending):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, 'codex')
                    self.add_command(root)
                    planned = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
                    self.assertEqual(0, planned.returncode, planned.stderr)
                    step = json.loads(planned.stdout)
                    leaf = "import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); signal.signal(signal.SIGINT,signal.SIG_IGN); Path('detached.pid').write_text(str(os.getpid())); time.sleep(60)"
                    middle = "import subprocess,sys; subprocess.Popen([sys.executable,'-c',sys.argv[1]],start_new_session=True)"
                    leader = "import subprocess,sys,time; from pathlib import Path; subprocess.run([sys.executable,'-c',sys.argv[1],sys.argv[2]],start_new_session=True); exec(\"while not Path('detached.pid').exists(): time.sleep(0.01)\"); time.sleep(0 if sys.argv[3]=='normal' else 60)"
                    step['application']['command'] = [sys.executable, '-c', leader, middle, leaf, ending]
                    proc = subprocess.Popen(
                        fixtures.COMMAND + ['command', 'execute', '--timeout', '1' if ending == 'timeout' else '20'],
                        cwd=root, env=fixtures.CLI_ENV, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    )
                    pid = None
                    try:
                        proc.stdin.write(json.dumps(step))
                        proc.stdin.close()
                        proc.stdin = None
                        deadline = time.monotonic() + 5
                        while not (root / 'detached.pid').exists() and time.monotonic() < deadline:
                            time.sleep(0.02)
                        self.assertTrue((root / 'detached.pid').exists())
                        pid = int((root / 'detached.pid').read_text())
                        if ending in ('SIGTERM', 'SIGINT'):
                            proc.send_signal(getattr(signal, ending))
                        proc.wait(timeout=7)
                        expected = {'timeout': 124, 'SIGTERM': 143, 'SIGINT': 130, 'normal': 0}[ending]
                        self.assertEqual(expected, proc.returncode)
                        status = Path(f'/proc/{pid}/status')
                        if status.exists():
                            self.fail('detached descendant was not reaped: ' + status.read_text().splitlines()[2])
                    finally:
                        # Regression failures must not leave the intentionally detached probe running.
                        if pid is not None:
                            try:
                                os.kill(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        if proc.poll() is None:
                            proc.terminate()
                        proc.communicate(timeout=5)

    def test_preexisting_children_and_subreaper_state_are_preserved(self):
        import ctypes
        from ai_evo_skills.execution import run_delegated
        libc = ctypes.CDLL(None, use_errno=True)
        before, after = ctypes.c_int(), ctypes.c_int()
        self.assertEqual(0, libc.prctl(37, ctypes.byref(before), 0, 0, 0))
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            code = run_delegated([sys.executable, '-c', 'raise SystemExit(19)'], cwd=str(fixtures.ENGINE), env=os.environ.copy(), prompt=None, timeout=5)
            self.assertEqual(19, code)
            self.assertIsNone(unrelated.poll())
            self.assertEqual(0, libc.prctl(37, ctypes.byref(after), 0, 0, 0))
            self.assertEqual(before.value, after.value)
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=5)

    def test_timeout_rejects_invalid_values(self):
        for value in ('0', '-1', 'nan', 'inf', 'bad'):
            result = subprocess.run(fixtures.COMMAND + ['command', 'execute', '--timeout', value], env=fixtures.CLI_ENV, text=True, capture_output=True)
            self.assertEqual(2, result.returncode)
            self.assertIn('positive finite', result.stderr)
