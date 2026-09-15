import os
import subprocess
import tempfile
from pathlib import Path
import unittest

import yaml
import test_cli as fixtures


class PublicationPathsTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_init_rejects_invalid_targets_without_creating_project_files(self):
        for case in ('file', 'external-alias', 'dangling-alias', 'cyclic-alias', 'cyclic-chain',
                     'overlapping-targets', 'source-overlap'):
            for existing_ignores in (False, True):
                with self.subTest(case=case, existing_ignores=existing_ignores):
                    temporary, root = self.repository()
                    with temporary, tempfile.TemporaryDirectory() as external:
                        project = root / '.ai-evo-prj'
                        if existing_ignores:
                            project.mkdir()
                            (root / '.gitignore').write_text('# Preserve application rules\nlocal/\n')
                            (project / '.gitignore').write_text('# Preserve specification rules\nprivate/\n')
                        if case == 'file':
                            (root / '.agents').write_text('User file')
                        elif case == 'external-alias':
                            (root / '.agents').symlink_to(external, target_is_directory=True)
                        elif case == 'dangling-alias':
                            (root / '.agents').symlink_to('missing', target_is_directory=True)
                        elif case == 'cyclic-alias':
                            (root / '.agents').symlink_to('.agents', target_is_directory=True)
                        elif case == 'cyclic-chain':
                            (root / '.agents').symlink_to('.claude', target_is_directory=True)
                            (root / '.claude').symlink_to('.agents', target_is_directory=True)
                        elif case == 'overlapping-targets':
                            (root / 'clients').mkdir()
                            for name in ('.agents', '.claude'):
                                (root / name).symlink_to('clients', target_is_directory=True)
                        else:
                            (project / 'skills/catalog').mkdir(parents=True)
                            (root / '.agents').symlink_to('.ai-evo-prj/skills/catalog', target_is_directory=True)

                        def snapshot(directory):
                            result = {}
                            for path in directory.iterdir():
                                if path.name == '.git':
                                    continue
                                if path.is_symlink():
                                    result[path.name] = ('link', os.readlink(path))
                                elif path.is_dir():
                                    result[path.name] = snapshot(path)
                                else:
                                    result[path.name] = path.read_bytes()
                            return result

                        before = snapshot(root)
                        result = self.run_cli(root, 'init', '--namespace', 'abc', '--adapter', 'codex', '--adapter', 'claude')
                        self.assertEqual(1, result.returncode, result.stdout)
                        expected = {
                            'file': 'expected a directory',
                            'external-alias': 'outside the Git worktree',
                            'dangling-alias': 'expected a directory',
                            'cyclic-alias': 'expected a directory',
                            'cyclic-chain': 'expected a directory',
                            'overlapping-targets': 'unique after resolving filesystem aliases',
                            'source-overlap': 'must not overlap skill sources',
                        }[case]
                        self.assertIn(expected, result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
                        self.assertEqual(before, snapshot(root))
                        self.assertEqual([], list(Path(external).iterdir()))

    def test_changed_ordinary_target_is_ignored_without_hiding_user_files(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            self.add_command(root)
            config_path = root / '.ai-evo-skills.yaml'
            config = yaml.safe_load(config_path.read_text())
            config['targets'][0]['path'] = 'tools/[native] skills'
            config_path.write_text(yaml.safe_dump(config))
            directory = root / config['targets'][0]['path']
            # Missing directories are valid and must not be created by validation.
            result = self.run_cli(root, 'validate')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(directory.exists())
            before = (root / '.gitignore').read_bytes()
            result = self.run_cli(root, 'sync', '--dry-run')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(directory.exists())
            self.assertEqual(before, (root / '.gitignore').read_bytes())
            directory.mkdir(parents=True)
            (directory / 'notes.txt').write_text('User content')
            for _ in range(2):
                result = self.run_cli(root, 'sync')
                self.assertEqual(0, result.returncode, result.stderr)
                published = directory / 'abc-inspect'
                self.assertTrue(published.is_symlink())
                check = subprocess.run(['git', 'check-ignore', str(published)], cwd=root, capture_output=True)
                self.assertEqual(0, check.returncode, check.stderr)
                for visible in (directory / 'notes.txt', root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'):
                    check = subprocess.run(['git', 'check-ignore', str(visible)], cwd=root, capture_output=True)
                    self.assertEqual(1, check.returncode, check.stdout)
            before = (root / '.gitignore').read_bytes()
            result = self.run_cli(root, 'sync')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, (root / '.gitignore').read_bytes())

    def test_invalid_target_paths_fail_validation_and_planning_before_writes(self):
        for case in ('file', 'file-prefix', 'external-alias', 'root-alias', 'dangling-alias',
                     'cyclic-alias', 'cyclic-prefix', 'cyclic-chain'):
            with self.subTest(case=case):
                temporary, root = self.repository()
                with temporary, tempfile.TemporaryDirectory() as external:
                    self.initialize(root, 'codex')
                    self.add_command(root)
                    recipe = root / '.ai-evo-prj/skills/catalog/recipes/abc-recipe-flow'
                    recipe.mkdir()
                    (recipe / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
                    (recipe / 'recipe.yaml').write_text(yaml.safe_dump({
                        'version': '1.0', 'name': 'abc-recipe-flow', 'inputs': {},
                        'steps': [{'id': 'inspect', 'uses': 'abc-inspect'}],
                        'outputs': {'result': {'value': '${{ steps.inspect.output }}'}},
                    }))
                    path = root / 'destination'
                    if case in ('file', 'file-prefix'):
                        path.write_text('Preserve this file')
                    elif case.startswith('cyclic-'):
                        path.symlink_to('destination' if case != 'cyclic-chain' else 'cycle-peer')
                        if case == 'cyclic-chain':
                            (root / 'cycle-peer').symlink_to('destination')
                    else:
                        path.symlink_to({'external-alias': external, 'root-alias': str(root),
                                         'dangling-alias': 'missing-directory'}[case], target_is_directory=True)
                    config_path = root / '.ai-evo-skills.yaml'
                    config = yaml.safe_load(config_path.read_text())
                    config['targets'][0]['path'] = ('destination/skills'
                                                    if case in ('file-prefix', 'cyclic-prefix') else 'destination')
                    config_path.write_text(yaml.safe_dump(config))
                    before = (root / '.gitignore').read_bytes()
                    for arguments in (('validate',), ('command', 'plan', 'abc-inspect', '--adapter', 'codex'),
                                      ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex'),
                                      ('sync', '--dry-run'), ('sync',)):
                        result = self.run_cli(root, *arguments)
                        self.assertEqual(1, result.returncode, result.stdout)
                        expected = 'outside the Git worktree' if case in ('external-alias', 'root-alias') else 'expected a directory'
                        self.assertIn(expected, result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
                        self.assertEqual('', result.stdout)
                    self.assertEqual(before, (root / '.gitignore').read_bytes())
                    self.assertFalse((root / '.agents/skills').exists())
                    self.assertEqual([], list(Path(external).iterdir()))
                    if case in ('file', 'file-prefix'):
                        self.assertEqual('Preserve this file', path.read_text())
                    elif case.startswith('cyclic-'):
                        self.assertEqual('cycle-peer' if case == 'cyclic-chain' else 'destination', os.readlink(path))
                        if case == 'cyclic-chain':
                            self.assertEqual('destination', os.readlink(root / 'cycle-peer'))

    def test_symbolic_client_directory_supports_publication_and_removal(self):
        for shared in (False, True):
            with self.subTest(shared_project=shared):
                temporary, root = self.repository()
                with temporary:
                    if shared:
                        (root / 'specification').mkdir()
                        (root / '.ai-evo-prj').symlink_to('specification', target_is_directory=True)
                    self.initialize(root, 'codex')
                    self.add_command(root)
                    (root / 'nested/agents').mkdir(parents=True)
                    (root / '.agents').symlink_to('nested/agents', target_is_directory=True)
                    link = root / '.agents/skills/abc-inspect'
                    source = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect'
                    result = self.run_cli(root, 'sync')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue(link.is_symlink())
                    self.assertFalse(Path(os.readlink(link)).is_absolute())
                    self.assertEqual(source.resolve(), link.resolve())
                    self.assertEqual(fixtures.VALID_COMMAND, (link / 'SKILL.md').read_text())
                    result = self.run_cli(root, 'sync')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn('Already synchronized', result.stdout)
                    config_path = root / '.ai-evo-skills.yaml'
                    config = yaml.safe_load(config_path.read_text())
                    config['targets'][0]['enabled'] = False
                    config_path.write_text(yaml.safe_dump(config))
                    result = self.run_cli(root, 'sync')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertFalse(os.path.lexists(link))
                    self.assertEqual(fixtures.VALID_COMMAND, (source / 'SKILL.md').read_text())

    def test_targets_cannot_overlap_skill_sources(self):
        for target in ('.ai-evo-prj/skills/catalog', '.ai-evo-prj/skills/catalog/recipes',
                       '.ai-evo-prj/skills/catalog/commands/abc-inspect/tools',
                       '.ai-evo-prj/skills/custom/recipes', '.ai-evo-prj/skills', '.alias'):
            with self.subTest(target=target):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, 'codex')
                    self.add_command(root)
                    (root / '.alias').symlink_to('.ai-evo-prj/skills/catalog/recipes', target_is_directory=True)
                    config_path = root / '.ai-evo-skills.yaml'
                    config = yaml.safe_load(config_path.read_text())
                    config['targets'][0]['path'] = target
                    config_path.write_text(yaml.safe_dump(config))
                    skills = root / '.ai-evo-prj/skills'
                    def snapshot():
                        return {str(p.relative_to(skills)): p.read_bytes() if p.is_file() else None
                                for p in skills.rglob('*')}
                    before = snapshot()
                    for args in (('validate',), ('sync', '--dry-run'), ('sync',)):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode, result.stdout)
                        self.assertIn('target path must not overlap skill sources', result.stderr)
                    self.assertEqual(before, snapshot())

    def test_symbolic_publications_are_ignored_without_hiding_user_files(self):
        for before_init in (False, True):
            with self.subTest(alias_before_init=before_init):
                temporary, root = self.repository()
                with temporary:
                    physical = root / 'nested/[agents] space'
                    physical.mkdir(parents=True)
                    alias = root / '.agents'
                    if before_init:
                        alias.symlink_to(physical.relative_to(root), target_is_directory=True)
                    self.initialize(root, 'codex')
                    self.add_command(root)
                    if not before_init:
                        alias.symlink_to(physical.relative_to(root), target_is_directory=True)
                    (physical / 'skills').mkdir()
                    user_file = physical / 'skills/notes.txt'
                    user_file.write_text('User content')
                    ignore = root / '.gitignore'
                    original = ignore.read_bytes()
                    dry = self.run_cli(root, 'sync', '--dry-run')
                    self.assertEqual(0, dry.returncode, dry.stderr)
                    self.assertEqual(original, ignore.read_bytes())
                    for _ in range(2):
                        result = self.run_cli(root, 'sync')
                        self.assertEqual(0, result.returncode, result.stderr)
                        published = physical / 'skills/abc-inspect'
                        check = subprocess.run(['git', 'check-ignore', str(published)], cwd=root, capture_output=True)
                        self.assertEqual(0, check.returncode, check.stderr)
                        for visible in (user_file, root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'):
                            check = subprocess.run(['git', 'check-ignore', str(visible)], cwd=root, capture_output=True)
                            self.assertEqual(1, check.returncode, check.stdout)
                    content = ignore.read_bytes()
                    self.run_cli(root, 'sync')
                    self.assertEqual(content, ignore.read_bytes(), 'ignore updates must be idempotent')
