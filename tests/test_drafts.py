import unittest
import yaml
import test_cli as fixtures


class DraftTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_multiple_drafts_can_be_created_but_not_published_or_planned(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            for args in [('command', 'one'), ('recipe', 'two'), ('recipe', 'three', '--catalog'), ('effort-profile', 'careful')]:
                result = self.run_cli(root, 'create', *args)
                self.assertEqual(0, result.returncode, result.stderr)
            for path in (root / '.ai-evo-prj/skills').rglob('SKILL.md'):
                yaml.safe_load(path.read_text().split('---\n')[1])
            for path in (root / '.ai-evo-prj/skills').rglob('*.yaml'):
                yaml.safe_load(path.read_text())
            for args in [('validate',), ('sync',), ('command', 'plan', 'abc-one', '--adapter', 'codex')]:
                result = self.run_cli(root, *args)
                self.assertNotEqual(0, result.returncode)
                self.assertIn('TODO', result.stderr)
            result = self.run_cli(root, 'create', 'recipe', 'one')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / '.ai-evo-prj/skills/custom/recipes/abc-recipe-one').exists())
            result = self.run_cli(root, 'create', 'recipe', 'one')
            self.assertNotEqual(0, result.returncode)
            self.assertIn('already used', result.stderr)
            self.assertFalse((root / '.agents/skills').exists())

    def test_an_incomplete_profile_alone_blocks_validation(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.assertEqual(0, self.run_cli(root, 'create', 'effort-profile', 'draft').returncode)
            result = self.run_cli(root, 'validate')
            self.assertNotEqual(0, result.returncode)
            self.assertIn('unresolved TODO', result.stderr)
