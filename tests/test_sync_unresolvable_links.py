import os
import unittest

import test_cli as fixtures


class SyncUnresolvableLinksTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_unmanaged_cycles_survive_sync_and_do_not_block_managed_links(self):
        for adapter, target in (('codex', '.agents/skills'), ('claude', '.claude/skills')):
            with self.subTest(adapter=adapter):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, adapter)
                    self.add_command(root)
                    directory = root / target
                    directory.mkdir(parents=True)
                    links = {'self-loop': 'self-loop', 'cycle-a': 'cycle-b', 'cycle-b': 'cycle-a'}
                    for name, destination in links.items():
                        (directory / name).symlink_to(destination)
                    stale = directory / 'abc-obsolete'
                    stale.symlink_to(root / '.ai-evo-prj/skills/catalog/commands/abc-obsolete')
                    ignore = root / '.gitignore'
                    original_ignore = ignore.read_bytes()
                    result = self.run_cli(root, 'sync', '--dry-run')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn('would link:', result.stdout)
                    self.assertIn('would remove:', result.stdout)
                    self.assertTrue(stale.is_symlink())
                    self.assertFalse((directory / 'abc-inspect').exists())
                    self.assertEqual(original_ignore, ignore.read_bytes())
                    result = self.run_cli(root, 'sync')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertFalse(stale.is_symlink(), 'dangling managed links must still be removed')
                    self.assertEqual((root / '.ai-evo-prj/skills/catalog/commands/abc-inspect').resolve(),
                                     (directory / 'abc-inspect').resolve())
                    result = self.run_cli(root, 'sync')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn('Already synchronized.', result.stdout)
                    for name, destination in links.items():
                        self.assertEqual(destination, os.readlink(directory / name))

    def test_cycle_colliding_with_a_skill_is_rejected_before_any_writes(self):
        for adapter, target in (('codex', '.agents/skills'), ('claude', '.claude/skills')):
            with self.subTest(adapter=adapter):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, adapter)
                    self.add_command(root)
                    directory = root / target
                    directory.mkdir(parents=True)
                    collision = directory / 'abc-inspect'
                    collision.symlink_to(collision.name)
                    stale = directory / 'abc-obsolete'
                    stale.symlink_to(root / '.ai-evo-prj/skills/catalog/commands/abc-obsolete')
                    original_ignore = (root / '.gitignore').read_bytes()
                    original_links = {path.name: os.readlink(path) for path in directory.iterdir()}
                    for arguments in (('sync', '--dry-run'), ('sync',)):
                        with self.subTest(arguments=arguments):
                            result = self.run_cli(root, *arguments)
                            self.assertEqual(1, result.returncode)
                            self.assertIn('collision with unmanaged file, directory or symlink', result.stderr)
                            self.assertNotIn('Traceback', result.stderr)
                            self.assertEqual('', result.stdout)
                            self.assertEqual(original_ignore, (root / '.gitignore').read_bytes())
                            self.assertEqual(original_links,
                                             {path.name: os.readlink(path) for path in directory.iterdir()})
