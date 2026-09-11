import unittest
from pathlib import Path

import yaml
import test_cli as fixtures
from ai_evo_skills import cli


class YamlLoadingTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_duplicate_nested_policy_is_rejected_before_publication_or_planning(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            path = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            path.write_text(path.read_text().replace('workspace: read-only', 'workspace: read-only\n  workspace: read-write'))
            for arguments in (('validate',), ('sync',), ('command', 'plan', 'abc-inspect', '--adapter', 'codex')):
                result = self.run_cli(root, *arguments)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("duplicate key 'workspace'", result.stderr)
                self.assertNotIn('Traceback', result.stderr)
            self.assertFalse((root / '.agents/skills').exists())

    def test_duplicate_config_and_frontmatter_keys_are_rejected(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            config = root / '.ai-evo-skills.yaml'
            original = config.read_text()
            config.write_text(original + '\nnamespace: xyz\n')
            result = self.run_cli(root, 'validate')
            self.assertNotEqual(0, result.returncode)
            self.assertIn("duplicate key 'namespace'", result.stderr)
            config.write_text(original)
            skill = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            skill.write_text(skill.read_text().replace('name: abc-inspect', 'name: abc-other\nname: abc-inspect'))
            result = self.run_cli(root, 'validate')
            self.assertNotEqual(0, result.returncode)
            self.assertIn("duplicate key 'name'", result.stderr)

    def test_ordinary_aliases_and_explicit_merge_overrides_remain_valid(self):
        from ai_evo_skills.yaml_loading import load_strict_yaml
        data = load_strict_yaml('base: &base {workspace: read-only, network: disabled}\npolicy: {<<: *base, workspace: read-write}\ncopy: *base\n')
        self.assertEqual({'workspace': 'read-write', 'network': 'disabled'}, data['policy'])
        self.assertEqual(data['base'], data['copy'])
        for text in ('x: 1\nx: 2', 'x: {a: 1, a: 2}', 'x: {<<: {a: 1}, <<: {a: 2}}'):
            with self.subTest(text=text), self.assertRaisesRegex(yaml.YAMLError, 'duplicate key'):
                load_strict_yaml(text)
