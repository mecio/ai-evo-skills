import json
import unittest
import yaml
import test_cli as fixtures
from test_claude_policy import options
from ai_evo_skills.claude_policy import require_claude_grants, ClaudePolicyError


class ProjectCapabilitiesTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_project_grants_fail_closed_and_preserve_denies(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'claude', 'codex')
            self.add_command(root)
            project = root / '.ai-evo-prj'
            config = project / 'skills/config/execution-capabilities.yaml'
            config.write_text(yaml.safe_dump({'version': '1.0', 'capabilities': {
                'abc.local': {'script': 'local-helper', 'operation': 'commit',
                              'arguments': True, 'workspaces': ['read-write']}}}))
            script = project / 'scripts/local-helper'
            script.parent.mkdir(exist_ok=True)
            script.write_text('#!/bin/sh\nexit 0\n')
            script.chmod(0o755)
            skill = project / 'skills/catalog/commands/abc-inspect/SKILL.md'
            body = fixtures.VALID_COMMAND.replace('workspace: read-only', 'workspace: read-write').replace(
                'network: disabled', 'network: disabled\n  capabilities: [abc.local]\n  deny-capabilities: [git.remote-write, github.remote-write]')
            skill.write_text(body)
            result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'claude')
            self.assertEqual(0, result.returncode, result.stderr)
            args = options(json.loads(result.stdout)['application']['cli_arguments'])
            self.assertIn('Bash(.ai-evo-prj/scripts/local-helper commit *)', args['--allowedTools'])
            self.assertIn('Bash(git push *)', args['--disallowedTools'])
            self.assertNotIn('Bash', args['--allowedTools'].split(','))
            for adapter, content, expected in [
                ('codex', body, 'cannot enforce capability'),
                ('claude', body.replace('workspace: read-write', 'workspace: read-only'), 'cannot enforce capability'),
                ('claude', body.replace('[git.remote-write, github.remote-write]', '[abc.local]'), 'explicitly denied'),
            ]:
                skill.write_text(content)
                result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', adapter)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(expected, result.stderr)
            skill.write_text(body)
            script.unlink()
            result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'claude')
            self.assertNotEqual(0, result.returncode)
            self.assertIn('executable project script', result.stderr)

    def test_glob_denies_are_disjoint_only_with_provable_prefix(self):
        grant = 'Bash(.ai-evo-prj/scripts/local-helper commit *)'
        require_claude_grants(['--allowedTools', grant, '--disallowedTools',
                               'Bash(gh api * --method POST *)'], [grant], 'abc.local')
        for deny in ['Bash(*)', 'Bash(.ai-evo-prj/scripts/* commit *)']:
            with self.assertRaises(ClaudePolicyError):
                require_claude_grants(['--allowedTools', grant, '--disallowedTools', deny], [grant], 'abc.local')
