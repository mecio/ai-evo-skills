from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml
import test_cli as fixtures


class LauncherTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_launcher_uses_installed_environment_under_kernel_read_only_restrictions(self):
        if not sys.platform.startswith('linux'):
            self.skipTest('Landlock requires Linux')
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            # This child denies writes across the filesystem, including the real uv cache.
            # Unlike chmod, the kernel restriction also applies to privileged processes.
            sandbox = r'''
import ctypes, errno, os, sys
libc = ctypes.CDLL(None, use_errno=True)
class Ruleset(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64)]
abi = libc.syscall(444, 0, 0, 1)
if abi < 1:
    sys.exit(77)
mask = (1 << 1) | sum(1 << i for i in range(4, 13))
if abi >= 3:
    mask |= 1 << 14
rules = Ruleset(mask)
fd = libc.syscall(444, ctypes.byref(rules), ctypes.sizeof(rules), 0)
assert fd >= 0, ctypes.get_errno()
class PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int)]
null_fd = os.open('/dev/null', os.O_PATH)
rule = PathRule(1 << 1, null_fd)
assert libc.syscall(445, fd, 1, ctypes.byref(rule), 0) == 0, ctypes.get_errno()
os.close(null_fd)
assert libc.prctl(38, 1, 0, 0, 0) == 0
assert libc.syscall(446, fd, 0) == 0, ctypes.get_errno()
os.close(fd)
try:
    open('must-not-exist', 'w')
except PermissionError:
    pass
else:
    raise AssertionError('filesystem is writable')
os.execv(sys.argv[1], sys.argv[1:])
'''
            result = subprocess.run(
                [sys.executable, '-c', sandbox, str(fixtures.ENGINE / 'bin/ai-evo-skills'),
                 'command', 'plan', 'abc-inspect', '--adapter', 'codex'],
                cwd=root, text=True, capture_output=True,
            )
            if result.returncode == 77:
                self.skipTest('Landlock unavailable on this kernel')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual('abc-inspect', json.loads(result.stdout)['command'])
            self.assertFalse((root / 'must-not-exist').exists())

    def test_launcher_bootstrap_preserves_arguments_and_does_not_retry_failed_installed_cli(self):
        with tempfile.TemporaryDirectory(prefix='ai-evo-launcher.') as temporary:
            root = Path(temporary)
            (root / 'bin').mkdir()
            launcher = root / 'bin/ai-evo-skills'
            launcher.write_bytes((fixtures.ENGINE / 'bin/ai-evo-skills').read_bytes())
            launcher.chmod(0o755)
            uv = root / 'bin/uv'
            uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            uv.chmod(0o755)
            env = {**os.environ, 'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH']}
            result = subprocess.run([str(launcher), 'command', 'plan', 'a b'], env=env, text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(['run', '--frozen', '--project', str(root), 'ai-evo-skills', 'command', 'plan', 'a b'], result.stdout.splitlines())
            installed = root / '.venv/bin/ai-evo-skills'
            installed.parent.mkdir(parents=True)
            installed.write_text('#!/bin/sh\nexit 23\n')
            installed.chmod(0o755)
            result = subprocess.run([str(launcher), '--version'], env=env, text=True, capture_output=True)
            self.assertEqual(23, result.returncode)
            self.assertEqual('', result.stdout)

