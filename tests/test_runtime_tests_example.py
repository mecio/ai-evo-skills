import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_cli as fixtures
from ai_evo_skills.recipe_runtime import advance_recipe, skipped_output


EXAMPLE = fixtures.ENGINE / 'examples/runtime-tests'
HELPER = EXAMPLE / 'scripts/acme-worktree-context.py'


class WorktreeContextTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ai-evo-context.')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'application'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.config = self.base / 'contexts.json'

    def configure(self, context='php83', entries=None):
        self.config.write_text(json.dumps({
            'schema_version': 1,
            'worktrees': entries if entries is not None else [{'root': str(self.root), 'context': context}],
        }))

    def run_helper(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(HELPER), '--config', str(self.config), *args],
            cwd=cwd or self.root, capture_output=True, text=True,
        )

    def test_tokens_and_json_agree_for_both_contexts(self):
        for context in ('php72', 'php83'):
            with self.subTest(context=context):
                self.configure(context)
                token = self.run_helper('--field', 'context')
                self.assertEqual(0, token.returncode, token.stderr)
                self.assertEqual(context + '\n', token.stdout)
                self.assertEqual('', token.stderr)
                result = self.run_helper()
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual({'schema_version': 1, 'git_root': str(self.root), 'context': context},
                                 json.loads(result.stdout))
                self.assertEqual(result.stdout, self.run_helper().stdout)

    def test_subdirectory_and_symlink_use_canonical_root_not_branch(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.configure(entries=[{'root': str(alias), 'context': 'php72'}])
        subdirectory = self.root / 'src'
        subdirectory.mkdir()
        subprocess.run(['git', 'symbolic-ref', 'HEAD', 'refs/heads/php83-migration'],
                       cwd=self.root, check=True)
        result = self.run_helper('--field', 'context', cwd=alias / 'src')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('php72\n', result.stdout)

    def test_linked_worktree_has_its_own_context(self):
        subprocess.run(['git', '-c', 'user.name=Example', '-c', 'user.email=example@example.test',
                        'commit', '-q', '--allow-empty', '-m', 'Initial'], cwd=self.root, check=True)
        linked = self.base / 'linked'
        subprocess.run(['git', 'worktree', 'add', '-q', '-b', 'migration', str(linked)],
                       cwd=self.root, check=True)
        self.configure(entries=[{'root': str(self.root), 'context': 'php72'},
                                {'root': str(linked), 'context': 'php83'}])
        result = self.run_helper('--field', 'context', cwd=linked)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('php83\n', result.stdout)
        self.assertEqual('php72\n', self.run_helper('--field', 'context').stdout)

    def test_invalid_or_unknown_mapping_never_emits_a_success_token(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        invalid_entries = [
            [],
            [{'root': str(self.base / 'other'), 'context': 'php83'}],
            [{'root': str(self.root), 'context': 'php8'}],
            [{'root': 'relative/path', 'context': 'php83'}],
            [{'root': str(self.root), 'context': 'php72'}, {'root': str(alias), 'context': 'php83'}],
        ]
        for entries in invalid_entries:
            with self.subTest(entries=entries):
                self.configure(entries=entries)
                result = self.run_helper('--field', 'context')
                self.assertEqual(1, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertIn('error:', result.stderr)

    def test_missing_malformed_config_and_non_repository_fail(self):
        for content in (None, '{', 'null'):
            with self.subTest(content=content):
                if content is not None:
                    self.config.write_text(content)
                result = self.run_helper('--field', 'context')
                self.assertEqual(1, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertIn('error:', result.stderr)
        self.configure()
        result = self.run_helper(cwd=self.base)
        self.assertEqual(1, result.returncode)
        self.assertEqual('', result.stdout)


class RuntimeTestsCatalogTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_catalog_coexists_publishes_and_routes_for_both_coordinators(self):
        temporary, root = self.repository()
        with temporary:
            result = self.run_cli(root, 'init', '--namespace', 'acme', '--adapter', 'codex', '--adapter', 'claude')
            self.assertEqual(0, result.returncode, result.stderr)
            specs = root / '.ai-evo-prj'
            for catalog in (fixtures.ENGINE / 'examples/acme/catalog', EXAMPLE / 'catalog'):
                shutil.copytree(catalog, specs / 'skills/catalog', dirs_exist_ok=True)
            shutil.copytree(EXAMPLE / 'scripts', specs / 'scripts')
            config = specs / 'skills/config/acme-worktrees.json'
            for action in ('validate', 'sync'):
                result = self.run_cli(root, action)
                self.assertEqual(0, result.returncode, result.stderr)
            names = [p.name for kind in ('commands', 'recipes') for p in (EXAMPLE / 'catalog' / kind).iterdir()]
            for client in ('.agents', '.claude'):
                for name in names:
                    self.assertTrue((root / client / 'skills' / name).is_symlink())
            for adapter in ('codex', 'claude'):
                result = self.run_cli(root, 'recipe', 'plan', 'acme-recipe-test-legacy-and-unit', '--adapter', adapter)
                self.assertEqual(0, result.returncode, result.stderr)
                plan = json.loads(result.stdout)
                for context in ('php72', 'php83'):
                    config.write_text(json.dumps({'schema_version': 1, 'worktrees': [
                        {'root': str(root), 'context': context},
                    ]}))
                    detected = subprocess.run([sys.executable, str(specs / 'scripts/acme-worktree-context.py'),
                                               '--field', 'context'], cwd=root, text=True, capture_output=True)
                    self.assertEqual(0, detected.returncode, detected.stderr)
                    records, executed = [], []
                    while True:
                        transition = advance_recipe({'plan': plan, 'results': records})
                        if transition['status'] == 'complete':
                            self.assertEqual('report result', transition['output'])
                            break
                        if transition['status'] == 'skipped':
                            records.append(transition['result'])
                            continue
                        self.assertEqual('ready', transition['status'])
                        step = transition['step']
                        sid = step['id']
                        executed.append(sid)
                        if sid != 'report':
                            self.assertEqual('codex', step['application']['executor'])
                        if sid in ('legacy_tests', 'unit_tests'):
                            self.assertEqual(detected.stdout, step['with']['context'])
                        if sid == 'report':
                            self.assertEqual('legacy_tests result', step['with']['legacy_result'])
                            if context == 'php72':
                                self.assertEqual(skipped_output('unit_tests'), json.loads(step['with']['unit_result']))
                            else:
                                self.assertEqual('unit_tests result', step['with']['unit_result'])
                        output = detected.stdout if sid == 'php_context' else sid + ' result'
                        records.append({'step': sid, 'status': 'succeeded', 'output': output})
                    self.assertEqual(['php_context', 'legacy_tests'] +
                                     (['unit_tests'] if context == 'php83' else []) + ['report'], executed)
                failed = advance_recipe({'plan': plan, 'results': [
                    {'step': 'php_context', 'status': 'succeeded', 'output': 'php83\n'},
                    {'step': 'legacy_tests', 'status': 'failed', 'exit_code': 7},
                ]})
                self.assertEqual('failed', failed['status'])


if __name__ == '__main__':
    unittest.main()
