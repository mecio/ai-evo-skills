import os
from pathlib import Path
import unittest

import yaml
import test_cli as fixtures


class PublicationPathsTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

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
