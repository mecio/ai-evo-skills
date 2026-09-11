import json
import unittest

import yaml
import test_cli as fixtures


class SessionPolicyTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_codex_persistence_follows_profile_independently_of_workspace_policy(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            profile_path = root / '.ai-evo-prj/skills/config/effort-profiles/abc-default.yaml'
            profile = yaml.safe_load(profile_path.read_text())
            skill_path = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            for workspace in ('read-only', 'read-write'):
                skill_path.write_text(fixtures.VALID_COMMAND.replace('workspace: read-only', f'workspace: {workspace}'))
                for reuse in ('never', 'correction-only', 'always'):
                    with self.subTest(workspace=workspace, reuse=reuse):
                        profile['execution']['reuse-session'] = reuse
                        profile_path.write_text(yaml.safe_dump(profile))
                        result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
                        self.assertEqual(0, result.returncode, result.stderr)
                        app = json.loads(result.stdout)['application']
                        sandbox_index = app['cli_arguments'].index('--sandbox')
                        self.assertEqual('read-only' if workspace == 'read-only' else 'workspace-write', app['cli_arguments'][sandbox_index + 1])
                        self.assertEqual(reuse == 'never', '--ephemeral' in app['cli_arguments'])
                        self.assertEqual(reuse, app['session']['reuse'])
                        self.assertEqual(reuse != 'never', app['session']['resume_allowed'])
