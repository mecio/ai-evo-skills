"""Opt-in native policy checks. Codex sandbox checks do not make model requests."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import unittest

import test_cli as fixtures


@unittest.skipUnless(os.environ.get('AI_EVO_NATIVE_SANDBOX_TESTS') == '1', 'set AI_EVO_NATIVE_SANDBOX_TESTS=1 for native sandbox checks')
class NativeSandboxTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_codex_native_workspace_and_network_restrictions(self):
        if not shutil.which('codex'):
            self.skipTest('Codex CLI not installed')
        temporary, root = self.repository()
        with temporary, socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(5)
            port = listener.getsockname()[1]
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass  # Positive control: the endpoint is reachable outside the sandbox.
            self.initialize(root, 'codex')
            self.add_command(root)
            for workspace in ('read-only', 'read-write'):
                with self.subTest(workspace=workspace):
                    skill = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
                    skill.write_text(fixtures.VALID_COMMAND.replace('workspace: read-only', f'workspace: {workspace}'))
                    result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
                    self.assertEqual(0, result.returncode, result.stderr)
                    arguments = json.loads(result.stdout)['application']['cli_arguments']
                    sandbox = arguments[arguments.index('--sandbox') + 1]
                    probe = '''import json,socket,sys
from pathlib import Path
try:
    Path('native-marker').write_text('allowed')
    wrote = True
except PermissionError:
    wrote = False
try:
    connection = socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=1)
    connection.close()
    connected = True
except OSError:
    connected = False
print(json.dumps({'wrote': wrote, 'connected': connected}))
'''
                    native = subprocess.run(
                        ['codex', 'sandbox', '-c', f'sandbox_mode="{sandbox}"', '-c', 'sandbox_workspace_write.network_access=false', '--', sys.executable, '-c', probe, str(port)],
                        cwd=root, text=True, capture_output=True, timeout=10,
                    )
                    unavailable = ('Failed RTM_NEWADDR', 'setting up uid map', 'No permissions to create new namespace')
                    if native.returncode and any(message in native.stderr for message in unavailable):
                        self.skipTest('native sandbox unavailable: host forbids the required Linux namespaces')
                    self.assertEqual(0, native.returncode, native.stderr)
                    observed = json.loads(native.stdout)
                    self.assertEqual(workspace == 'read-write', observed['wrote'])
                    self.assertFalse(observed['connected'])
