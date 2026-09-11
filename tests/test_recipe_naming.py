import copy
import json
import os
from pathlib import Path
import shutil
import unittest

import yaml
from jsonschema import Draft202012Validator

import test_cli as fixtures
from ai_evo_skills.execution import ExecutionError
from ai_evo_skills.recipe_runtime import advance_recipe


class RecipeNamingTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def add_recipe(self, root, name='abc-recipe-flow', collection='catalog', uses='abc-inspect'):
        directory = root / '.ai-evo-prj/skills' / collection / 'recipes' / name
        directory.mkdir(parents=True)
        (directory / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL.replace('abc-recipe-flow', name))
        (directory / 'recipe.yaml').write_text(yaml.safe_dump({
            'version': '1.0', 'name': name, 'executor': 'current', 'inputs': {},
            'steps': [{'id': 'inspect', 'uses': uses}],
            'outputs': {'result': {'value': '${{ steps.inspect.output }}'}},
        }))
        return directory

    def test_create_uses_recipe_prefix_in_both_collections_and_keeps_command_names(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            for name, args, collection in (('my-review', [], 'custom'), ('team-review', ['--catalog'], 'catalog'),
                                           ('demo-my-review', [], 'custom')):
                result = self.run_cli(root, 'create', 'recipe', name, *args)
                self.assertEqual(0, result.returncode, result.stderr)
                full = f'abc-recipe-{name}'
                directory = root / f'.ai-evo-prj/skills/{collection}/recipes' / full
                text = (directory / 'SKILL.md').read_text()
                self.assertEqual(full, yaml.safe_load(text.split('---\n')[1])['name'])
                self.assertEqual(full, yaml.safe_load((directory / 'recipe.yaml').read_text())['name'])
                self.assertIn('recipe plan ' + full, text)
                self.assertIn('/' + full, text)
                self.assertFalse(directory.with_name('abc-' + name).exists())
            result = self.run_cli(root, 'create', 'command', 'my-review')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / '.ai-evo-prj/skills/catalog/commands/abc-my-review/SKILL.md').is_file())

    def test_create_rejects_prefixed_names_without_writes_and_counts_full_length(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            skills = root / '.ai-evo-prj/skills'
            before = sorted(str(p) for p in skills.rglob('*'))
            for name, diagnostic in (
                ('recipe-my-review', 'unprefixed recipe name'),
                ('recipe-recipe-my-review', 'unprefixed recipe name'),
                ('abc-recipe-my-review', 'unprefixed recipe name'),
                ('abc-my-review', 'unprefixed recipe name'),
                ('demo-recipe-my-review', "does not match project namespace 'abc'"),
                ('a' * 54, '64 characters'),
            ):
                for options in ([], ['--catalog']):
                    with self.subTest(name=name, options=options):
                        result = self.run_cli(root, 'create', 'recipe', name, *options)
                        self.assertEqual(1, result.returncode, result.stdout)
                        self.assertIn(diagnostic, result.stderr)
                        if 'my-review' in name:
                            self.assertIn("'my-review'", result.stderr)
                        self.assertEqual(before, sorted(str(p) for p in skills.rglob('*')))
            result = self.run_cli(root, 'create', 'recipe', 'a' * 53)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((skills / 'custom/recipes' / ('abc-recipe-' + 'a' * 53)).is_dir())

    def test_legacy_recipes_are_rejected_by_all_catalog_entrypoints(self):
        for collection in ('catalog', 'custom'):
            with self.subTest(collection=collection):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, 'codex', 'claude')
                    self.add_command(root)
                    legacy = self.add_recipe(root, 'abc-flow', collection)
                    before = {p.name: p.read_bytes() for p in legacy.iterdir()}
                    for args in (('validate',), ('sync',), ('sync', '--dry-run'),
                                 ('recipe', 'plan', 'abc-flow', '--adapter', 'codex'),
                                 ('command', 'plan', 'abc-inspect', '--adapter', 'codex'),
                                 ('profile', 'resolve', '--adapter', 'codex'), ('create', 'command', 'new')):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode, result.stdout)
                        self.assertIn("expected 'abc-recipe-flow'", result.stderr)
                    self.assertEqual(before, {p.name: p.read_bytes() for p in legacy.iterdir()})
                    self.assertFalse((root / '.agents/skills').exists())

    def test_names_must_match_in_directory_frontmatter_and_yaml(self):
        for field in ('directory', 'frontmatter', 'yaml', 'foreign'):
            temporary, root = self.repository()
            with self.subTest(field=field), temporary:
                self.initialize(root, 'codex')
                self.add_command(root)
                directory = self.add_recipe(root, 'demo-recipe-flow' if field == 'foreign' else 'abc-recipe-flow')
                if field == 'directory':
                    directory.rename(directory.with_name('abc-flow'))
                elif field in ('frontmatter', 'yaml'):
                    path = directory / ('SKILL.md' if field == 'frontmatter' else 'recipe.yaml')
                    path.write_text(path.read_text().replace('abc-recipe-flow', 'abc-flow'))
                result = self.run_cli(root, 'validate')
                self.assertEqual(1, result.returncode, result.stdout)
                self.assertIn("expected 'abc-recipe-flow'", result.stderr)

    def test_nested_references_and_runtime_names_require_explicit_migration(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            self.add_recipe(root)
            outer = self.add_recipe(root, 'abc-recipe-outer', uses='abc-flow')
            result = self.run_cli(root, 'validate')
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn("expected 'abc-recipe-flow'", result.stderr)
            path = outer / 'recipe.yaml'
            path.write_text(path.read_text().replace('uses: abc-flow', 'uses: abc-recipe-flow'))
            for adapter in ('codex', 'claude'):
                result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-outer', '--adapter', adapter)
                self.assertEqual(0, result.returncode, result.stderr)
                plan = json.loads(result.stdout)
                self.assertEqual('abc-recipe-outer', plan['recipe'])
                self.assertEqual('abc-inspect', plan['execution']['steps'][0]['uses'])
                self.assertEqual('inspect.inspect', plan['execution']['steps'][0]['id'])
                self.assertEqual('ready', advance_recipe({'plan': plan, 'results': []})['status'])
                legacy = copy.deepcopy(plan)
                legacy['recipe'] = 'abc-outer'
                with self.assertRaisesRegex(ExecutionError, "expected 'abc-recipe-outer'"):
                    advance_recipe({'plan': legacy, 'results': []})
            result = self.run_cli(root, 'recipe', 'plan', 'abc-flow', '--adapter', 'codex')
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn("expected 'abc-recipe-flow'", result.stderr)

    def test_sync_removes_legacy_managed_links_and_publishes_only_new_names(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            directory = self.add_recipe(root)
            for client in ('.agents', '.claude'):
                target = root / client / 'skills'
                target.mkdir(parents=True)
                # Both dangling pre-migration links and aliases to the new source are managed.
                source = directory.with_name('abc-flow') if client == '.agents' else directory
                (target / 'abc-flow').symlink_to(os.path.relpath(source, target), target_is_directory=True)
                (target / 'notes.txt').write_text('User content')
            result = self.run_cli(root, 'sync', '--dry-run')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('would remove:', result.stdout)
            self.assertTrue((root / '.agents/skills/abc-flow').is_symlink())
            result = self.run_cli(root, 'sync')
            self.assertEqual(0, result.returncode, result.stderr)
            for client in ('.agents', '.claude'):
                target = root / client / 'skills'
                self.assertFalse(os.path.lexists(target / 'abc-flow'))
                self.assertEqual(directory.resolve(), (target / 'abc-recipe-flow').resolve())
                self.assertTrue((target / 'abc-inspect').is_symlink())
                self.assertEqual('User content', (target / 'notes.txt').read_text())

    def test_recipe_schema_requires_marker_but_uses_still_accepts_commands(self):
        schema = json.loads((fixtures.ENGINE / 'schemas/recipe.schema.json').read_text())
        validator = Draft202012Validator(schema)
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            recipe = yaml.safe_load((self.add_recipe(root) / 'recipe.yaml').read_text())
            self.assertTrue(validator.is_valid(recipe))
            for name in ('abc-flow', 'abc-recipe-', 'abc-recipe-' + 'a' * 54):
                recipe['name'] = name
                self.assertFalse(validator.is_valid(recipe))

    def test_acme_review_example_plans_and_publishes_for_both_clients(self):
        temporary, root = self.repository()
        with temporary:
            result = self.run_cli(root, 'init', '--namespace', 'acme', '--adapter', 'codex', '--adapter', 'claude')
            self.assertEqual(0, result.returncode, result.stderr)
            shutil.copytree(fixtures.ENGINE / 'examples/acme/catalog',
                            root / '.ai-evo-prj/skills/catalog', dirs_exist_ok=True)
            result = self.run_cli(root, 'validate')
            self.assertEqual(0, result.returncode, result.stderr)
            for adapter in ('codex', 'claude'):
                result = self.run_cli(root, 'recipe', 'plan', 'acme-recipe-reviewed-change',
                                      '--adapter', adapter, '--input', 'target=HEAD')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(['acme-review', 'acme-report-review'],
                                 [step['uses'] for step in json.loads(result.stdout)['execution']['steps']])
            result = self.run_cli(root, 'sync')
            self.assertEqual(0, result.returncode, result.stderr)
            for client in ('.agents', '.claude'):
                for name in ('acme-detect-changes', 'acme-review', 'acme-report-review',
                             'acme-recipe-reviewed-change', 'acme-recipe-review-security-if-changed'):
                    self.assertTrue((root / client / 'skills' / name).is_symlink())
