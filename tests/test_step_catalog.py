from __future__ import annotations

import json
import unittest

import yaml

import test_cli as fixtures


VALID_STEP = fixtures.VALID_COMMAND.replace("abc-inspect", "abc-step-approval").replace(
    "ai-evo-kind: command\n", "ai-evo-kind: step\n"
).replace(
    "ai-evo-recipe-only: false\n", "ai-evo-recipe-only: true\n"
)


class StepCatalogTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_step_is_recipe_only_and_is_not_published_as_a_direct_skill(self) -> None:
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            step = root / ".ai-evo-prj/skills/catalog/recipes/_steps/abc-step-approval/SKILL.md"
            step.parent.mkdir(parents=True)
            step.write_text(VALID_STEP)

            recipe = root / ".ai-evo-prj/skills/catalog/recipes/abc-recipe-flow"
            recipe.mkdir(parents=True)
            (recipe / "SKILL.md").write_text(fixtures.VALID_FLOW_SKILL)
            (recipe / "recipe.yaml").write_text(yaml.safe_dump({
                "version": "1.0",
                "name": "abc-recipe-flow",
                "inputs": {},
                "steps": [{"id": "approval", "uses": "abc-step-approval"}],
                "outputs": {"result": {"value": "${{ steps.approval.output }}"}},
            }))

            self.assertEqual(0, self.run_cli(root, "validate").returncode)
            direct = self.run_cli(root, "command", "plan", "abc-step-approval", "--adapter", "codex")
            self.assertEqual(1, direct.returncode)
            self.assertIn("unknown command", direct.stderr)

            planned = self.run_cli(
                root, "recipe", "plan", "abc-recipe-flow", "--adapter", "codex"
            )
            self.assertEqual(0, planned.returncode, planned.stderr)
            execution = json.loads(planned.stdout)["execution"]["steps"]
            self.assertEqual("abc-step-approval", execution[0]["uses"])

            self.assertEqual(0, self.run_cli(root, "sync").returncode)
            self.assertFalse((root / ".agents/skills/abc-step-approval").exists())
            self.assertTrue((root / ".agents/skills/abc-recipe-flow").is_symlink())

    def test_create_step_uses_the_step_catalog_and_metadata(self) -> None:
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            result = self.run_cli(root, "create", "step", "approval")
            self.assertEqual(0, result.returncode, result.stderr)
            skill = root / ".ai-evo-prj/skills/catalog/recipes/_steps/abc-step-approval/SKILL.md"
            frontmatter = yaml.safe_load(skill.read_text().split("---", 2)[1])
            self.assertEqual("abc-step-approval", frontmatter["name"])
            self.assertEqual("step", frontmatter["metadata"]["ai-evo-kind"])
            self.assertIs(True, frontmatter["metadata"]["ai-evo-recipe-only"])

    def test_recipe_only_metadata_must_match_the_catalog_kind(self) -> None:
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            command.parent.mkdir(parents=True)
            command.write_text(fixtures.VALID_COMMAND.replace(
                "ai-evo-recipe-only: false", "ai-evo-recipe-only: true"
            ))
            result = self.run_cli(root, "validate")
            self.assertEqual(1, result.returncode)
            self.assertIn("ai-evo-recipe-only must be the boolean false for commands", result.stderr)

    def test_step_name_requires_the_step_marker(self) -> None:
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            step = root / ".ai-evo-prj/skills/catalog/recipes/_steps/abc-approval/SKILL.md"
            step.parent.mkdir(parents=True)
            step.write_text(VALID_STEP.replace("abc-step-approval", "abc-approval"))
            result = self.run_cli(root, "validate")
            self.assertEqual(1, result.returncode)
            self.assertIn("step name must use abc-step-<name>", result.stderr)


if __name__ == "__main__":
    unittest.main()
