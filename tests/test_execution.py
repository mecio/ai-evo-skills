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


class ExecutionTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def command_plan(self, root):
        result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def execute(self, root, step, *args):
        return subprocess.run(
            fixtures.COMMAND + ['command', 'execute', *args], cwd=root,
            env=fixtures.CLI_ENV, input=json.dumps(step), text=True, capture_output=True,
        )

    def test_session_translation_and_resume_authorization(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            profile_path = root / '.ai-evo-prj/skills/config/effort-profiles/abc-default.yaml'
            profile = yaml.safe_load(profile_path.read_text())
            for reuse in ('never', 'correction-only', 'always'):
                with self.subTest(reuse=reuse):
                    profile['execution']['reuse-session'] = reuse
                    profile_path.write_text(yaml.safe_dump(profile))
                    step = self.command_plan(root)
                    self.assertEqual(reuse == 'never', '--ephemeral' in step['application']['cli_arguments'])
                    self.assertEqual(reuse, step['application']['session']['reuse'])
                    step['application']['command'] = [sys.executable, '-c', 'import sys; print(sys.argv[1:])']
                    denied = self.execute(root, step, '--resume-session', 'test-session')
                    self.assertEqual(reuse == 'always', denied.returncode == 0)
                    resumed = self.execute(root, step, '--resume-session', 'test-session', '--correction')
                    self.assertEqual(reuse != 'never', resumed.returncode == 0)
                    if reuse != 'never':
                        self.assertIn("'resume', 'test-session', '-'", resumed.stdout)

    def test_handoff_uses_snapshot_and_blocks_second_planning(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            launcher_guard = subprocess.run(
                [str(fixtures.ENGINE / 'bin/ai-evo-skills'), 'command', 'plan', 'abc-inspect', '--adapter', 'codex'],
                cwd=root, env={**fixtures.CLI_ENV, 'AI_EVO_EXECUTION_HANDOFF': 'resolved'},
                text=True, capture_output=True,
            )
            self.assertNotEqual(0, launcher_guard.returncode)
            self.assertIn('handoff is already resolved', launcher_guard.stderr)
            step = self.command_plan(root)
            # Removing the catalog proves execute does not invoke the planner again.
            Path(step['skill_path']).unlink()
            probe = '''import json, os, subprocess, sys
payload = json.load(sys.stdin)
assert payload['plan']['handoff']['allow_planning'] is False
assert payload['plan']['handoff']['planning']['command'] == 'resolved'
assert os.getcwd() == payload['plan']['application']['working_directory']
assert os.environ['AI_EVO_EXECUTION_HANDOFF'] == 'resolved'
for operation in ('command', 'recipe'):
    result = subprocess.run([sys.executable, '-m', 'ai_evo_skills.cli', operation, 'plan', 'abc-inspect', '--adapter', 'codex'], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'handoff is already resolved' in result.stderr, result.stderr
print('executed without replanning')
'''
            step['application']['command'] = [sys.executable, '-c', probe]
            result = self.execute(root, step)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('executed without replanning', result.stdout)
            step['with'] = {'target': {'type': 'ai-evo-step-output', 'step': 'previous'}}
            result = self.execute(root, step)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('resolve all step output references', result.stderr)

    def test_recipe_handoff_preserves_sequence_outputs_and_failure(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            skill = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            skill.write_text(fixtures.VALID_COMMAND.replace('executor: current', 'executor: claude'))
            second = skill.parent.parent / 'abc-verify/SKILL.md'
            second.parent.mkdir()
            second.write_text(fixtures.VALID_COMMAND.replace('abc-inspect', 'abc-verify').replace('executor: current', 'executor: codex').replace('inputs: {}', 'inputs:\n  review:\n    description: Prior result\n    required: true'))
            recipe = root / '.ai-evo-prj/skills/catalog/recipes/abc-flow'
            recipe.mkdir()
            (recipe / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
            (recipe / 'recipe.yaml').write_text(yaml.safe_dump({
                'version': '1.0', 'name': 'abc-flow', 'executor': 'codex', 'inputs': {},
                'steps': [{'id': 'review', 'uses': 'abc-inspect'}, {'id': 'verify', 'uses': 'abc-verify', 'with': {'review': '${{ steps.review.output }}'}}],
                'outputs': {'result': {'value': '${{ steps.verify.output }}'}},
            }))
            result = self.run_cli(root, 'recipe', 'plan', 'abc-flow', '--adapter', 'codex')
            self.assertEqual(0, result.returncode, result.stderr)
            steps = json.loads(result.stdout)['execution']['steps']
            self.assertEqual(['claude', 'codex'], [s['application']['executor'] for s in steps])
            for step in steps:
                self.assertEqual('resolved', step['handoff']['planning']['recipe'])
                self.assertEqual({'workspace': 'read-only', 'network': 'disabled'}, step['application']['execution_policy'])
            steps[0]['application']['command'] = [sys.executable, '-c', 'print("review result")']
            first = self.execute(root, steps[0])
            self.assertEqual(0, first.returncode, first.stderr)
            steps[1]['with']['review'] = first.stdout.strip()
            steps[1]['application']['command'] = [sys.executable, '-c', 'import json,sys; assert json.load(sys.stdin)["plan"]["with"]["review"] == "review result"; sys.exit(17)']
            second = self.execute(root, steps[1])
            self.assertEqual(17, second.returncode)
