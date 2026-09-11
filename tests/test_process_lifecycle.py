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

    def test_timeout_rejects_invalid_values(self):
        for value in ('0', '-1', 'nan', 'inf', 'bad'):
            result = subprocess.run(fixtures.COMMAND + ['command', 'execute', '--timeout', value], env=fixtures.CLI_ENV, text=True, capture_output=True)
            self.assertEqual(2, result.returncode)
            self.assertIn('positive finite', result.stderr)
