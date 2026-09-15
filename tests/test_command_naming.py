import json
import unittest

import yaml

import test_cli as fixtures


class CommandNamingTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_created_command_can_be_completed_planned_and_published(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            result = self.run_cli(root, 'create', 'command', 'team-review')
            self.assertEqual(0, result.returncode, result.stderr)
            name = 'abc-cmd-team-review'
            directory = root / '.ai-evo-prj/skills/catalog/commands' / name
            skill = directory / 'SKILL.md'
            text = skill.read_text()
            self.assertEqual(name, yaml.safe_load(text.split('---\n')[1])['name'])
            self.assertIn('command plan ' + name, text)
            self.assertIn('/' + name, text)
            self.assertFalse(directory.with_name('abc-team-review').exists())
            skill.write_text(text.replace('TODO', 'Review tracked changes'))
            result = self.run_cli(root, 'validate')
            self.assertEqual(0, result.returncode, result.stderr)
            for adapter in ('codex', 'claude'):
                result = self.run_cli(root, 'command', 'plan', name, '--adapter', adapter)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(name, json.loads(result.stdout)['command'])
            result = self.run_cli(root, 'sync')
            self.assertEqual(0, result.returncode, result.stderr)
            for client in ('.agents', '.claude'):
                self.assertEqual(directory.resolve(), (root / client / 'skills' / name).resolve())
            before = skill.read_bytes()
            result = self.run_cli(root, 'create', 'command', 'team-review')
            self.assertEqual(1, result.returncode)
            self.assertIn('already used', result.stderr)
            self.assertEqual(before, skill.read_bytes())
            result = self.run_cli(root, 'create', 'recipe', 'team-review', '--catalog')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / '.ai-evo-prj/skills/catalog/recipes/abc-recipe-team-review').is_dir())

    def test_create_rejects_prefixed_names_without_writing(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            skills = root / '.ai-evo-prj/skills'
            before = sorted(str(p) for p in skills.rglob('*'))
            for name, diagnostic in (
                ('cmd', 'unprefixed command name'),
                ('cmd-review', 'unprefixed command name'),
                ('cmd-cmd-review', 'unprefixed command name'),
                ('abc-cmd-review', 'unprefixed command name'),
                ('abc-cmd-cmd-review', 'unprefixed command name'),
                ('abc-review', 'unprefixed command name'),
                ('demo-cmd-review', "does not match project namespace 'abc'"),
                ('Review', 'lowercase ASCII'),
            ):
                with self.subTest(name=name):
                    result = self.run_cli(root, 'create', 'command', name)
                    self.assertEqual(1, result.returncode, result.stdout)
                    self.assertIn(diagnostic, result.stderr)
                    if 'review' in name:
                        self.assertIn("'review'", result.stderr)
                    self.assertEqual(before, sorted(str(p) for p in skills.rglob('*')))

    def test_length_limit_includes_namespace_and_cmd_marker(self):
        for namespace in ('abc', 'abcdef'):
            temporary, root = self.repository()
            with self.subTest(namespace=namespace), temporary:
                result = self.run_cli(root, 'init', '--namespace', namespace, '--adapter', 'codex')
                self.assertEqual(0, result.returncode, result.stderr)
                prefix = namespace + '-cmd-'
                short = 'a' * (64 - len(prefix))
                result = self.run_cli(root, 'create', 'command', short + 'a')
                self.assertEqual(1, result.returncode)
                self.assertIn('64 characters', result.stderr)
                commands = root / '.ai-evo-prj/skills/catalog/commands'
                self.assertEqual([], list(commands.iterdir()))
                result = self.run_cli(root, 'create', 'command', short)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue((commands / (prefix + short) / 'SKILL.md').is_file())
