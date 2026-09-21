import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_cli as fixtures


class RecoveryExampleTest(unittest.TestCase):
    def test_demo_recovers_prefix_and_rejects_changed_dependencies(self):
        for extra, recovered, next_step in (([], ['review', 'check_review'], 'report'),
                                            (['--invalidate-review'], [], 'review')):
            with self.subTest(extra=extra):
                result = subprocess.run([sys.executable, str(fixtures.ENGINE / 'examples/recovery/demo.py'), *extra],
                                        text=True, capture_output=True, timeout=90)
                self.assertEqual(0, result.returncode, result.stderr)
                report = json.loads(result.stdout)
                self.assertTrue(report['simulated'])
                self.assertTrue(report['source_unchanged'])
                self.assertEqual(recovered, report['recovered_steps'])
                self.assertEqual(next_step, report['next_step'])

    def test_helper_preserves_bytes_and_rejects_empty_or_invalid_utf8(self):
        helper = fixtures.ENGINE / 'examples/acme/scripts/acme-check-review-output.py'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'review.txt'
            for content, valid in ((b'Finding: example.  \r\n', True), (b' \n', False), (b'\xff', False)):
                with self.subTest(content=content):
                    path.write_bytes(content)
                    result = subprocess.run([sys.executable, str(helper), '--input', str(path)], capture_output=True)
                    self.assertEqual(0 if valid else 1, result.returncode)
                    self.assertEqual(content if valid else b'', result.stdout)
                    if not valid:
                        self.assertIn(b'error:', result.stderr)


class AcmeStepExampleTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_internal_step_is_not_published_or_directly_plannable(self):
        temporary, root = self.repository()
        with temporary:
            result = self.run_cli(root, 'init', '--namespace', 'acme', '--adapter', 'codex', '--adapter', 'claude')
            self.assertEqual(0, result.returncode, result.stderr)
            shutil.copytree(fixtures.ENGINE / 'examples/acme/catalog', root / '.ai-evo-prj/skills/catalog', dirs_exist_ok=True)
            for action in ('validate', 'sync'):
                result = self.run_cli(root, action)
                self.assertEqual(0, result.returncode, result.stderr)
            name = 'acme-step-check-review-output'
            for client in ('.agents', '.claude'):
                self.assertFalse((root / client / 'skills' / name).exists())
                self.assertTrue((root / client / 'skills/acme-cmd-review').is_symlink())
            result = self.run_cli(root, 'command', 'plan', name, '--adapter', 'codex', '--input', 'review=example')
            self.assertNotEqual(0, result.returncode)
            for adapter in ('codex', 'claude'):
                result = self.run_cli(root, 'recipe', 'plan', 'acme-recipe-reviewed-change', '--adapter', adapter)
                self.assertEqual(0, result.returncode, result.stderr)
                step = json.loads(result.stdout)['execution']['steps'][1]
                self.assertEqual(name, step['uses'])
                self.assertEqual('current', step['application']['mode'])
                self.assertEqual(adapter, step['application']['executor'])


if __name__ == '__main__':
    unittest.main()
