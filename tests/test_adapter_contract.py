import json
from pathlib import Path
import shutil
import unittest

import yaml
import test_cli as fixtures
from ai_evo_skills.execution import validate_plan


class AdapterContractTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_policy_arguments_match_execution_contract(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            engine = root / 'engine'
            for directory in ('adapters', 'schemas'):
                shutil.copytree(fixtures.ENGINE / directory, engine / directory)
            (root / '.ai-evo').unlink()
            (root / '.ai-evo').symlink_to(engine, target_is_directory=True)
            path = engine / 'adapters/codex.yaml'
            original = path.read_text()
            for policy in ('workspace-read-only', 'workspace-read-write', 'network-disabled'):
                for arguments, valid in (([''], False), (['--option', ''], False),
                                         ([], True), (['--option=value'], True)):
                    with self.subTest(policy=policy, arguments=arguments):
                        adapter = yaml.safe_load(original)
                        adapter['execution-policy-translation'][policy]['cli-arguments'] = arguments
                        path.write_text(yaml.safe_dump(adapter))
                        skill = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
                        skill.write_text(fixtures.VALID_COMMAND.replace('workspace: read-only',
                                         'workspace: read-write' if policy == 'workspace-read-write' else 'workspace: read-only'))
                        checked = self.run_cli(root, 'validate')
                        planned = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
                        if valid:
                            self.assertEqual(0, checked.returncode, checked.stderr)
                            self.assertEqual(0, planned.returncode, planned.stderr)
                            validate_plan(json.loads(planned.stdout))
                        else:
                            for result in (checked, planned):
                                self.assertEqual(1, result.returncode, result.stdout)
                                self.assertIn('cli-arguments', result.stderr)
                            self.assertEqual('', planned.stdout)

    def test_resume_templates_are_checked_before_any_plan_is_produced(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            engine = root / 'engine'
            for directory in ('adapters', 'schemas'):
                shutil.copytree(fixtures.ENGINE / directory, engine / directory)
            (root / '.ai-evo').unlink()
            (root / '.ai-evo').symlink_to(engine, target_is_directory=True)
            adapter_path = engine / 'adapters/codex.yaml'
            adapter = yaml.safe_load(adapter_path.read_text())
            for arguments, valid in ((['resume'], False), (['--resume=session'], False),
                                     (['resume', '<session-id>', '-'], True),
                                     (['--resume=<session-id>'], True)):
                with self.subTest(arguments=arguments):
                    adapter['invocation']['resume-arguments'] = arguments
                    adapter_path.write_text(yaml.safe_dump(adapter))
                    checked = self.run_cli(root, 'validate')
                    planned = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
                    if valid:
                        self.assertEqual(0, checked.returncode, checked.stderr)
                        self.assertEqual(0, planned.returncode, planned.stderr)
                        validate_plan(json.loads(planned.stdout))
                    else:
                        for result in (checked, planned):
                            self.assertNotEqual(0, result.returncode)
                            self.assertIn('resume-arguments', result.stderr)
                        self.assertEqual('', planned.stdout)
