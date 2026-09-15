from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ENGINE = Path(__file__).resolve().parents[1]
CLI_ENV = {**os.environ, "PYTHONPATH": str(ENGINE / "tooling/src")}
COMMAND = ["python3", "-m", "ai_evo_skills.cli"]
VALID_COMMAND = """---
name: abc-inspect
description: Inspect a target and report the result.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Inspect

## Purpose
Inspect a target.
## Interface
```yaml ai-evo-interface
executor: current
execution-policy:
  workspace: read-only
  network: disabled
inputs: {}
```
## Procedure
1. Inspect.
## Expected output
A report.
## Constraints
- Do not write.
## Success criteria
- A report exists.
## Examples
```text
/abc-inspect
```
"""
VALID_RECIPE_SKILL = """---
name: abc-recipe-loop
description: Demonstrates a recipe that is structurally valid but cyclic.
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Cyclic recipe

## Purpose
Demonstrate cycle detection.
## Interface
The formal interface is defined in `recipe.yaml`.
## Procedure
1. Plan the recipe.
## Expected output
A result.
## Constraints
- Run sequentially.
## Success criteria
- A result exists.
## Examples
```text
/abc-recipe-loop
```
"""
VALID_FLOW_SKILL = """---
name: abc-recipe-flow
description: Coordinates an example command with a specific adapter.
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Adapter-specific flow

## Purpose
Coordinate an example command.
## Interface
The formal interface is defined in `recipe.yaml`.
## Procedure
1. Plan and run the recipe.
## Expected output
A command result.
## Constraints
- Run sequentially.
## Success criteria
- The command completes.
## Examples
```text
/abc-recipe-flow
```
"""


class CliIntegrationTest(unittest.TestCase):
    def repository(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-evo-test.")
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".ai-evo").symlink_to(ENGINE, target_is_directory=True)
        return temporary, root

    def run_cli(self, root, *arguments):
        return subprocess.run(COMMAND + list(arguments), cwd=root, env=CLI_ENV, text=True, capture_output=True)

    def initialize(self, root, *adapters):
        arguments = ["init", "--namespace", "abc"]
        for adapter in adapters:
            arguments.extend(["--adapter", adapter])
        result = self.run_cli(root, *arguments)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_version_reports_beta_release(self):
        result = subprocess.run(COMMAND + ["--version"], env=CLI_ENV, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ai-evo-skills 0.1.0-beta.4", result.stdout.strip())

    def add_command(self, root):
        path = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(VALID_COMMAND)

    def test_init_creates_minimum_valid_project(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            self.assertTrue((root / ".ai-evo-prj/entrypoint.md").is_file())
            self.assertTrue((root / ".ai-evo-prj/skills/config/effort-profiles/abc-default.yaml").is_file())
            self.assertIn("!AGENTS.md", (root / ".gitignore").read_text())
            self.assertEqual(0, self.run_cli(root, "validate").returncode)

    def test_missing_entrypoint_is_invalid(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            (root / ".ai-evo-prj/entrypoint.md").unlink()
            result = self.run_cli(root, "validate")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing project entrypoint", result.stderr)

    def test_disabling_target_removes_managed_links(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex", "claude")
            self.add_command(root)
            self.assertEqual(0, self.run_cli(root, "sync").returncode)
            link = root / ".claude/skills/abc-inspect"
            self.assertTrue(link.is_symlink())
            config_path = root / ".ai-evo-skills.yaml"
            config = yaml.safe_load(config_path.read_text())
            next(target for target in config["targets"] if target["adapter"] == "claude")["enabled"] = False
            config_path.write_text(yaml.safe_dump(config, sort_keys=False))
            self.assertEqual(0, self.run_cli(root, "sync").returncode)
            self.assertFalse(link.is_symlink())

    def test_nested_targets_are_rejected_without_changing_the_catalog(self):
        for reverse, alias in ((False, False), (True, False), (False, True)):
            with self.subTest(reverse=reverse, alias=alias):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, 'codex', 'claude')
                    self.add_command(root)
                    if alias:
                        (root / '.shared').mkdir()
                        (root / '.alias').symlink_to('.shared', target_is_directory=True)
                    path = root / '.ai-evo-skills.yaml'
                    config = yaml.safe_load(path.read_text())
                    config['targets'][0]['path'] = '.shared'
                    config['targets'][1]['path'] = ('.alias' if alias else '.shared') + '/abc-inspect/tools'
                    if reverse:
                        config['targets'].reverse()
                    path.write_text(yaml.safe_dump(config))
                    for args in (('validate',), ('sync', '--dry-run'), ('sync',)):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode, result.stdout)
                        self.assertIn('target paths must not overlap', result.stderr)
                    source = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect'
                    self.assertEqual(['SKILL.md'], sorted(p.name for p in source.iterdir()))
                    self.assertEqual(VALID_COMMAND, (source / 'SKILL.md').read_text())
                    self.assertFalse(os.path.lexists(root / '.shared/abc-inspect'))

    def test_nested_targets_are_rejected_after_publication(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            path = root / '.ai-evo-skills.yaml'
            config = yaml.safe_load(path.read_text())
            config['targets'][0]['path'] = '.shared'
            path.write_text(yaml.safe_dump(config))
            self.assertEqual(0, self.run_cli(root, 'sync').returncode)
            config['targets'][1]['path'] = '.shared/abc-inspect/tools'
            path.write_text(yaml.safe_dump(config))
            for args in (('validate',), ('sync', '--dry-run'), ('sync',)):
                result = self.run_cli(root, *args)
                self.assertEqual(1, result.returncode, result.stdout)
                self.assertIn('target paths must not overlap', result.stderr)
            source = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect'
            self.assertEqual(['SKILL.md'], sorted(p.name for p in source.iterdir()))
            self.assertEqual(VALID_COMMAND, (source / 'SKILL.md').read_text())
            self.assertTrue((root / '.shared/abc-inspect').is_symlink())
            self.assertTrue((root / '.claude/skills/abc-inspect').is_symlink())

    def test_equivalent_target_paths_fail_before_sync_writes(self):
        for alias in (".agents/./skills", ".agents/skills/", "alias/skills"):
            with self.subTest(alias=alias):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, "codex", "claude")
                    self.add_command(root)
                    if alias.startswith("alias/"):
                        (root / ".agents").mkdir()
                        (root / "alias").symlink_to(root / ".agents", target_is_directory=True)
                    config_path = root / ".ai-evo-skills.yaml"
                    config = yaml.safe_load(config_path.read_text())
                    config["targets"][1]["path"] = alias
                    config_path.write_text(yaml.safe_dump(config))
                    for arguments in (("validate",), ("sync", "--dry-run"), ("sync",)):
                        result = self.run_cli(root, *arguments)
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("target paths must be unique", result.stderr)
                    self.assertFalse((root / ".agents/skills").exists())
                    self.assertFalse((root / ".claude/skills").exists())

    def test_command_plan_enforces_restrictive_policy_with_delegation(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            self.add_command(root)
            result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "codex")
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual("delegated", plan["application"]["mode"])
            self.assertEqual("stdin", plan["application"]["prompt_delivery"])
            arguments = plan["application"]["cli_arguments"]
            self.assertIn("read-only", arguments)
            self.assertIn("tools.web_search=false", arguments)

    def test_init_rejects_incompatible_entrypoint_without_partial_files(self):
        temporary, root = self.repository()
        with temporary:
            (root / "AGENTS.md").write_text("unrelated instructions\n")
            result = self.run_cli(root, "init", "--namespace", "abc", "--adapter", "codex")
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".ai-evo-skills.yaml").exists())
            self.assertFalse((root / ".ai-evo-prj").exists())

    def test_sync_refuses_unmanaged_collision(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            self.add_command(root)
            collision = root / ".agents/skills/abc-inspect"
            collision.parent.mkdir(parents=True)
            collision.write_text("unmanaged\n")
            result = self.run_cli(root, "sync")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("unmanaged\n", collision.read_text())

    def test_validate_rejects_recipe_cycle(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            recipe = root / ".ai-evo-prj/skills/custom/recipes/abc-recipe-loop"
            recipe.mkdir(parents=True)
            (recipe / "SKILL.md").write_text(VALID_RECIPE_SKILL)
            (recipe / "recipe.yaml").write_text("""version: "1.0"
name: abc-recipe-loop
executor: current
inputs: {}
steps:
  - id: recurse
    uses: abc-recipe-loop
outputs:
  result:
    value: "${{ steps.recurse.output }}"
""")
            result = self.run_cli(root, "validate")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("recipe cycle: abc-recipe-loop -> abc-recipe-loop", result.stderr)

    def test_malformed_child_inputs_report_validation_errors_without_traceback(self):
        for definition in ("broken", "null", "[]", "42"):
            with self.subTest(definition=definition):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, "codex")
                    self.add_command(root)
                    command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
                    command.write_text(VALID_COMMAND.replace(
                        "inputs: {}", f"inputs:\n  target: {definition}"
                    ))
                    recipe = root / ".ai-evo-prj/skills/catalog/recipes/abc-recipe-flow"
                    recipe.mkdir()
                    (recipe / "SKILL.md").write_text(VALID_FLOW_SKILL)
                    (recipe / "recipe.yaml").write_text(yaml.safe_dump({
                        "version": "1.0", "name": "abc-recipe-flow", "executor": "current",
                        "inputs": {}, "steps": [{"id": "inspect", "uses": "abc-inspect"}],
                        "outputs": {"result": {"value": "${{ steps.inspect.output }}"}},
                    }))
                    for arguments in (
                        ("validate",), ("sync",),
                        ("recipe", "plan", "abc-recipe-flow", "--adapter", "codex"),
                    ):
                        result = self.run_cli(root, *arguments)
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("target: definition must be a mapping", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse((root / ".agents/skills").exists())

    def test_invalid_policy_value_types_report_errors_without_traceback(self):
        for dimension, original in (("workspace", "read-only"), ("network", "disabled")):
            for value in ("[]", "{}", "null", "true", "42"):
                with self.subTest(dimension=dimension, value=value):
                    temporary, root = self.repository()
                    with temporary:
                        self.initialize(root, "codex")
                        self.add_command(root)
                        command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
                        command.write_text(VALID_COMMAND.replace(
                            f"{dimension}: {original}", f"{dimension}: {value}"
                        ))
                        result = self.run_cli(root, "validate")
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("invalid execution-policy", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_nested_recipe_inputs_preserve_schema_diagnostics(self):
        for inputs in ([], None, "broken", 42, {"target": []}):
            with self.subTest(inputs=inputs):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, "codex")
                    self.add_command(root)
                    for name, used, definitions in (
                        ("abc-recipe-flow", "abc-inspect", inputs),
                        ("abc-recipe-outer", "abc-recipe-flow", {}),
                    ):
                        recipe = root / ".ai-evo-prj/skills/catalog/recipes" / name
                        recipe.mkdir()
                        (recipe / "SKILL.md").write_text(VALID_FLOW_SKILL.replace("abc-recipe-flow", name))
                        (recipe / "recipe.yaml").write_text(yaml.safe_dump({
                            "version": "1.0", "name": name, "executor": "current",
                            "inputs": definitions, "steps": [{"id": "run", "uses": used}],
                            "outputs": {"result": {"value": "${{ steps.run.output }}"}},
                        }))
                    for arguments in (
                        ("validate",), ("sync",),
                        ("recipe", "plan", "abc-recipe-outer", "--adapter", "codex"),
                    ):
                        result = self.run_cli(root, *arguments)
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("recipe.yaml:inputs", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse((root / ".agents/skills").exists())

    def test_recipe_is_published_only_to_its_coordinator(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex", "claude")
            self.add_command(root)
            recipe = root / ".ai-evo-prj/skills/catalog/recipes/abc-recipe-flow"
            recipe.mkdir(parents=True)
            (recipe / "SKILL.md").write_text(VALID_FLOW_SKILL)
            (recipe / "recipe.yaml").write_text("""version: "1.0"
name: abc-recipe-flow
executor: codex
inputs: {}
steps:
  - id: inspect
    uses: abc-inspect
outputs:
  result:
    value: "${{ steps.inspect.output }}"
""")
            self.assertEqual(0, self.run_cli(root, "sync").returncode)
            self.assertTrue((root / ".agents/skills/abc-recipe-flow").is_symlink())
            self.assertFalse((root / ".claude/skills/abc-recipe-flow").exists())
            rejected = self.run_cli(root, "recipe", "plan", "abc-recipe-flow", "--adapter", "claude")
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("requires coordinator adapter codex", rejected.stderr)

    def test_command_is_published_only_to_its_executor(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex", "claude")
            self.add_command(root)
            command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            command.write_text(command.read_text().replace("executor: current", "executor: codex"))
            self.assertEqual(0, self.run_cli(root, "sync").returncode)
            self.assertTrue((root / ".agents/skills/abc-inspect").is_symlink())
            self.assertFalse((root / ".claude/skills/abc-inspect").exists())

    def test_claude_read_only_policy_preserves_git_command_access(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex", "claude")
            self.add_command(root)
            command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            command.write_text(command.read_text().replace("executor: current", "executor: claude"))
            result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "codex")
            self.assertEqual(0, result.returncode, result.stderr)
            arguments = json.loads(result.stdout)["application"]["cli_arguments"]
            self.assertIn("dontAsk", arguments)
            self.assertTrue(any("Bash(.ai-evo/bin/ai-evo-git-read *)" in argument for argument in arguments))
            self.assertNotIn("--restricted", arguments)
            application = json.loads(result.stdout)["application"]
            self.assertEqual("stdin", application["prompt_delivery"])
            self.assertTrue(application["policy_instructions"])

    def test_read_only_git_wrapper_rejects_git_output_options(self):
        status = subprocess.run(
            [str(ENGINE / "bin/ai-evo-git-read"), "status"],
            cwd=ENGINE,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, status.returncode, status.stderr)
        with tempfile.TemporaryDirectory(prefix="ai-evo-git-read-test.") as temporary:
            output = Path(temporary) / "forbidden"
            rejected = subprocess.run(
                [str(ENGINE / "bin/ai-evo-git-read"), "diff", f"--output={output}"],
                cwd=ENGINE,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(0, rejected.returncode)
            self.assertFalse(output.exists())

    def test_git_wrapper_does_not_run_configured_external_programs(self):
        temporary, root = self.repository()
        with temporary:
            def git(*arguments, input=None):
                return subprocess.run(
                    ["git", *arguments], cwd=root, input=input,
                    text=True, capture_output=True, check=True,
                ).stdout.strip()

            marker = root / "unexpected-write"
            helper = root / "external-helper"
            helper.write_text("#!/bin/sh\ntouch unexpected-write\nexit 1\n")
            helper.chmod(0o755)
            tree = git("mktree", input="")
            commit = (
                f"tree {tree}\n"
                "author Test <test@example.test> 1700000000 +0000\n"
                "committer Test <test@example.test> 1700000000 +0000\n"
                "gpgsig -----BEGIN PGP SIGNATURE-----\n \n"
                " ZmFrZQ==\n -----END PGP SIGNATURE-----\n\nTest\n"
            )
            oid = git("hash-object", "-t", "commit", "-w", "--stdin", input=commit)
            git("update-ref", "HEAD", oid)
            git("config", "log.showSignature", "true")
            git("config", "gpg.program", str(helper))
            git("config", "core.fsmonitor", str(helper))
            for operation in (("log",), ("show", "HEAD"), ("status",)):
                with self.subTest(operation=operation):
                    result = subprocess.run(
                        [str(ENGINE / "bin/ai-evo-git-read"), *operation],
                        cwd=root, text=True, capture_output=True,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertFalse(marker.exists(), result.stderr)

    def test_git_wrapper_disables_clean_and_process_filters(self):
        for driver in ("clean", "process"):
            with self.subTest(driver=driver):
                temporary, root = self.repository()
                with temporary:
                    def git(*arguments):
                        return subprocess.run(
                            ["git", *arguments], cwd=root, text=True,
                            capture_output=True, check=True,
                        )

                    git("config", "user.name", "Test")
                    git("config", "user.email", "test@example.test")
                    (root / ".gitattributes").write_text("data.txt filter=custom\n")
                    (root / "data.txt").write_text("original\n")
                    git("add", ".gitattributes", "data.txt")
                    git("commit", "-qm", "Initial")
                    helper = root / "filter-helper"
                    helper.write_text("#!/bin/sh\ntouch unexpected-write\ncat\n")
                    helper.chmod(0o755)
                    included = root / "filters.config"
                    included.write_text(
                        f'[filter "custom"]\n{driver} = {helper}\nrequired = true\n'
                    )
                    git("config", "include.path", str(included))
                    (root / "data.txt").write_text("changed content\n")
                    for operation in ("diff", "status"):
                        result = subprocess.run(
                            [str(ENGINE / "bin/ai-evo-git-read"), operation],
                            cwd=root, text=True, capture_output=True,
                        )
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertIn("data.txt", result.stdout)
                        if operation == "diff":
                            self.assertIn("+changed content", result.stdout)
                        self.assertFalse((root / "unexpected-write").exists())

    def test_init_reuses_shared_project_configuration_across_worktrees(self):
        with tempfile.TemporaryDirectory(prefix="ai-evo-shared-test.") as temporary:
            base = Path(temporary)
            project = base / "project-specs"
            project.mkdir()
            repositories = []
            for name in ("first", "second"):
                root = base / name
                root.mkdir()
                subprocess.run(["git", "init", "-q"], cwd=root, check=True)
                (root / ".ai-evo").symlink_to(ENGINE, target_is_directory=True)
                (root / ".ai-evo-prj").symlink_to(project, target_is_directory=True)
                repositories.append(root)
            self.initialize(repositories[0], "codex")
            profile = project / "skills/config/effort-profiles/abc-default.yaml"
            original = profile.read_text()
            self.initialize(repositories[1], "codex")
            self.assertEqual(original, profile.read_text())
            self.assertEqual(0, self.run_cli(repositories[1], "validate").returncode)

    def test_published_recipe_rejects_a_disabled_command_executor(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex", "claude")
            self.add_command(root)
            command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            command.write_text(command.read_text().replace("executor: current", "executor: claude"))
            recipe = root / ".ai-evo-prj/skills/catalog/recipes/abc-recipe-flow"
            recipe.mkdir(parents=True)
            (recipe / "SKILL.md").write_text(VALID_FLOW_SKILL)
            (recipe / "recipe.yaml").write_text("""version: "1.0"
name: abc-recipe-flow
executor: codex
inputs: {}
steps:
  - id: inspect
    uses: abc-inspect
outputs:
  result:
    value: "${{ steps.inspect.output }}"
""")
            config_path = root / ".ai-evo-skills.yaml"
            config = yaml.safe_load(config_path.read_text())
            next(target for target in config["targets"] if target["adapter"] == "claude")["enabled"] = False
            config_path.write_text(yaml.safe_dump(config, sort_keys=False))
            result = self.run_cli(root, "validate")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("requires disabled adapter claude", result.stderr)
            self.assertNotEqual(0, self.run_cli(root, "sync").returncode)
            self.assertFalse((root / ".agents/skills/abc-recipe-flow").exists())

    def test_validate_ignores_unconfigured_adapter_files(self):
        with tempfile.TemporaryDirectory(prefix="ai-evo-adapter-test.") as temporary:
            base = Path(temporary)
            engine = base / "engine"
            shutil.copytree(
                ENGINE,
                engine,
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"),
            )
            (engine / "adapters/unused.yaml").write_text('version: "1.0"\nid: unused\n')
            root = base / "repository"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".ai-evo").symlink_to(engine, target_is_directory=True)
            self.initialize(root, "codex")
            self.assertEqual(0, self.run_cli(root, "validate").returncode)

    def test_configured_adapter_rejects_invalid_prompt_delivery(self):
        with tempfile.TemporaryDirectory(prefix="ai-evo-adapter-test.") as temporary:
            base = Path(temporary)
            engine = base / "engine"
            shutil.copytree(
                ENGINE,
                engine,
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"),
            )
            adapter = engine / "adapters/codex.yaml"
            adapter.write_text(adapter.read_text().replace("prompt-delivery: stdin", "prompt-delivery: invalid"))
            root = base / "repository"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".ai-evo").symlink_to(engine, target_is_directory=True)
            result = self.run_cli(root, "init", "--namespace", "abc", "--adapter", "codex")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("prompt-delivery", result.stderr)

    def test_unconfigured_executor_may_remain_dormant_in_catalog(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            self.add_command(root)
            command = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            command.write_text(command.read_text().replace("executor: current", "executor: claude"))
            self.assertEqual(0, self.run_cli(root, "validate").returncode)
            self.assertEqual(0, self.run_cli(root, "sync").returncode)
            self.assertFalse((root / ".agents/skills/abc-inspect").exists())

    def test_validate_rejects_symbolic_skill_directories(self):
        temporary, root = self.repository()
        with temporary, tempfile.TemporaryDirectory(prefix="ai-evo-outside-test.") as outside:
            self.initialize(root, "codex")
            external = Path(outside) / "abc-inspect"
            external.mkdir()
            (external / "SKILL.md").write_text(VALID_COMMAND)
            catalog = root / ".ai-evo-prj/skills/catalog/commands"
            (catalog / "abc-inspect").symlink_to(external, target_is_directory=True)
            result = self.run_cli(root, "validate")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("skill directories may not be symbolic links", result.stderr)
            self.assertNotEqual(0, self.run_cli(root, "sync").returncode)
            self.assertFalse((root / ".agents/skills/abc-inspect").exists())

    def test_symbolic_skill_files_fail_without_removing_published_links(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, "codex")
                    self.add_command(root)
                    self.assertEqual(0, self.run_cli(root, "sync").returncode)
                    published = root / ".agents/skills/abc-inspect"
                    original_target = os.readlink(published)
                    skill = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
                    external = root / "external.md"
                    if not broken:
                        external.write_text(skill.read_text())
                    skill.unlink()
                    skill.symlink_to(external)
                    for operation in ("validate", "sync"):
                        result = self.run_cli(root, operation)
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("skill files may not be symbolic links", result.stderr)
                    self.assertEqual(original_target, os.readlink(published))

    def test_validate_rejects_symbolic_catalog_directories(self):
        temporary, root = self.repository()
        with temporary, tempfile.TemporaryDirectory(prefix="ai-evo-catalog-test.") as outside:
            self.initialize(root, "codex")
            commands = root / ".ai-evo-prj/skills/catalog/commands"
            commands.rmdir()
            commands.symlink_to(Path(outside), target_is_directory=True)
            result = self.run_cli(root, "validate")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("canonical skill directory", result.stderr)

    def test_create_rejects_names_used_in_other_skill_collections(self):
        cases = (
            ("catalog/recipes", ("recipe", "inspect")),
            ("catalog/recipes", ("recipe", "inspect", "--catalog")),
            ("catalog/recipes", ("recipe", "flow")),
            ("custom/recipes", ("recipe", "flow", "--catalog")),
        )
        for collection, arguments in cases:
            with self.subTest(collection=collection, arguments=arguments):
                temporary, root = self.repository()
                with temporary:
                    self.initialize(root, "codex")
                    self.add_command(root)
                    skills = root / ".ai-evo-prj/skills"
                    collision_command = skills / "catalog/commands/abc-recipe-inspect"
                    collision_command.mkdir()
                    (collision_command / "SKILL.md").write_text(VALID_COMMAND.replace("abc-inspect", "abc-recipe-inspect"))
                    recipe = skills / collection / "abc-recipe-flow"
                    recipe.mkdir()
                    (recipe / "SKILL.md").write_text(VALID_FLOW_SKILL)
                    (recipe / "recipe.yaml").write_text(yaml.safe_dump({
                        "version": "1.0", "name": "abc-recipe-flow", "executor": "current",
                        "inputs": {}, "steps": [{"id": "run", "uses": "abc-inspect"}],
                        "outputs": {"result": {"value": "${{ steps.run.output }}"}},
                    }))
                    def snapshot():
                        return {
                            str(path.relative_to(skills)): path.read_bytes() if path.is_file() else None
                            for path in skills.rglob("*")
                        }
                    before = snapshot()
                    result = self.run_cli(root, "create", *arguments)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("already used", result.stderr)
                    self.assertEqual(before, snapshot())
                    self.assertEqual(0, self.run_cli(root, "validate").returncode)
                    self.assertEqual(0, self.run_cli(root, "create", "recipe", "fresh").returncode)

    def test_create_reads_every_template_before_writing(self):
        with tempfile.TemporaryDirectory(prefix="ai-evo-create-test.") as temporary:
            base = Path(temporary)
            engine = base / "engine"
            shutil.copytree(
                ENGINE,
                engine,
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"),
            )
            root = base / "repository"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".ai-evo").symlink_to(engine, target_is_directory=True)
            self.initialize(root, "codex")
            (engine / "templates/skills/recipe.tpl.yaml").unlink()
            result = self.run_cli(root, "create", "recipe", "flow")
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".ai-evo-prj/skills/custom/recipes/abc-recipe-flow").exists())

    def test_recipe_plan_uses_typed_step_output_references(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            command = VALID_COMMAND.replace(
                "inputs: {}",
                "inputs:\n  value:\n    description: Value to inspect.\n    default: initial",
            )
            path = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(command)
            recipe = root / ".ai-evo-prj/skills/catalog/recipes/abc-recipe-flow"
            recipe.mkdir(parents=True)
            (recipe / "SKILL.md").write_text(VALID_FLOW_SKILL)
            (recipe / "recipe.yaml").write_text("""version: "1.0"
name: abc-recipe-flow
executor: codex
inputs: {}
steps:
  - id: first
    uses: abc-inspect
  - id: second
    uses: abc-inspect
    with:
      value: "${{ steps.first.output }}"
outputs:
  result:
    value: "${{ steps.second.output }}"
""")
            result = self.run_cli(root, "recipe", "plan", "abc-recipe-flow", "--adapter", "codex")
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads(result.stdout)
            reference = {"type": "ai-evo-step-output", "step": "first"}
            self.assertEqual(reference, plan["execution"]["steps"][1]["with"]["value"])
            self.assertEqual(
                {"type": "ai-evo-step-output", "step": "second"}, plan["result"]
            )

    def test_init_preflights_structural_collisions(self):
        temporary, root = self.repository()
        with temporary:
            project = root / ".ai-evo-prj"
            project.mkdir()
            (project / "skills").write_text("collision\n")
            result = self.run_cli(root, "init", "--namespace", "abc", "--adapter", "codex")
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((project / "entrypoint.md").exists())
            self.assertFalse((project / "README.md").exists())
            self.assertFalse((root / ".ai-evo-skills.yaml").exists())

    def test_init_rejects_project_subdirectories_that_escape_through_symlinks(self):
        temporary, root = self.repository()
        with temporary, tempfile.TemporaryDirectory(prefix="ai-evo-init-outside-test.") as outside:
            project = root / ".ai-evo-prj"
            project.mkdir()
            (project / "skills").symlink_to(Path(outside), target_is_directory=True)
            result = self.run_cli(root, "init", "--namespace", "abc", "--adapter", "codex")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("resolves outside the project area", result.stderr)
            self.assertFalse((project / "entrypoint.md").exists())
            self.assertFalse((root / ".ai-evo-skills.yaml").exists())

    def test_init_rolls_back_when_a_late_write_fails(self):
        temporary, root = self.repository()
        with temporary:
            project = root / ".ai-evo-prj"
            project.mkdir()
            project_ignore = project / ".gitignore"
            project_ignore.write_text("existing\n")
            project_ignore.chmod(0o400)
            try:
                result = self.run_cli(root, "init", "--namespace", "abc", "--adapter", "codex")
            finally:
                project_ignore.chmod(0o600)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("existing\n", project_ignore.read_text())
            self.assertFalse((project / "entrypoint.md").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".ai-evo-skills.yaml").exists())
            self.assertFalse((root / ".gitignore").exists())

    def test_agent_skills_compatibility_field_is_validated(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "codex")
            self.add_command(root)
            skill = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            skill.write_text(skill.read_text().replace(
                "description: Inspect a target and report the result.",
                "description: Inspect a target and report the result.\ncompatibility: Requires Git.",
            ))
            self.assertEqual(0, self.run_cli(root, "validate").returncode)
            skill.write_text(skill.read_text().replace("compatibility: Requires Git.", "compatibility: [Git]"))
            result = self.run_cli(root, "validate")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("compatibility must be a non-empty string", result.stderr)


if __name__ == "__main__":
    unittest.main()
