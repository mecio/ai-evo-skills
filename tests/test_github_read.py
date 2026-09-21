import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml
import test_cli as fixtures
from test_claude_policy import options
from ai_evo_skills.execution import validate_plan


HELPER = fixtures.ENGINE / "bin/ai-evo-github-read"


class GitHubReadTest(unittest.TestCase):
    def test_only_fixed_read_commands_are_accepted(self):
        command = runpy.run_path(str(HELPER))["command"]
        self.assertEqual(["gh", "auth", "status", "--hostname", "github.com"], command(["auth-status"]))
        self.assertEqual(["gh", "repo", "view", "--json", "nameWithOwner,url,defaultBranchRef"],
                         command(["repo-view"]))
        self.assertEqual(["gh", "issue", "view", "12540", "--json",
                          "number,url,state,title,body,comments,labels,milestone,assignees"],
                         command(["issue-view", "12540"]))
        for args in ([], ["api"], ["auth-status", "--show-token"], ["issue-view", "0"],
                     ["issue-view", "-1"], ["issue-view", "1;touch marker"],
                     ["issue-view", "1", "--web"], ["repo-view", "--repo", "other/repo"],
                     ["issue-view", "https://github.com/other/repo/issues/1"]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                command(args)

    def test_auth_diagnostics_do_not_expose_tokens_and_environment_cannot_select_another_repo(self):
        main = runpy.run_path(str(HELPER))["main"]
        for code in (0, 1):
            with self.subTest(code=code), patch.object(sys, "argv", [str(HELPER), "auth-status"]), \
                    patch.dict(os.environ, {"GH_REPO": "other/repo", "GH_DEBUG": "api"}), \
                    patch("subprocess.run", return_value=subprocess.CompletedProcess(
                        [], code, b"secret-token", b"secret-token")) as run, \
                    patch("builtins.print") as output:
                self.assertEqual(code, main())
                env = run.call_args.kwargs["env"]
                self.assertNotIn("GH_REPO", env)
                self.assertNotIn("GH_DEBUG", env)
                self.assertEqual("1", env["GH_PROMPT_DISABLED"])
                self.assertNotIn("secret-token", str(output.call_args))
                self.assertEqual(60, run.call_args.kwargs["timeout"])

    def test_invalid_invocation_exits_without_launching_gh(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(HELPER), "issue-edit", "12540"],
                                    cwd=directory, capture_output=True, text=True,
                                    env={**os.environ, "PATH": ""})
            self.assertEqual(2, result.returncode)
            self.assertIn("no other arguments allowed", result.stderr)
            self.assertEqual([], list(Path(directory).iterdir()))


class GitHubReadPolicyTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_explicit_capabilities_and_planning_errors(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "claude", "codex")
            self.add_command(root)
            profile = root / ".ai-evo-prj/skills/config/effort-profiles/abc-default.yaml"
            data = yaml.safe_load(profile.read_text())
            data["resources"]["network"] = "auto"
            profile.write_text(yaml.safe_dump(data))
            skill = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            rule = "Bash(.ai-evo/bin/ai-evo-github-read issue-view *)"
            base = fixtures.VALID_COMMAND.replace("network: disabled", "network: enabled")
            for declarations in ("", "\n  capabilities: [github.issue-view]"):
                skill.write_text(base.replace("network: enabled", "network: enabled" + declarations))
                result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "claude")
                self.assertEqual(0, result.returncode, result.stderr)
                actual = options(json.loads(result.stdout)["application"]["cli_arguments"])
                validate_plan(json.loads(result.stdout))
                self.assertEqual(bool(declarations), rule in actual["--allowedTools"])
                self.assertNotIn("Bash(.ai-evo/bin/ai-evo-github-read *)", actual["--allowedTools"])
                self.assertNotIn("github-read repo-view", actual["--allowedTools"])
                self.assertNotIn("Bash", actual["--allowedTools"].split(","))
                self.assertNotIn("Bash(gh *)", actual["--allowedTools"])
                self.assertIn("Write", actual["--disallowedTools"])
                self.assertEqual("dontAsk", actual["--permission-mode"])
                self.assertEqual("none", actual["--permission-prompts"])
            declared = base.replace("network: enabled", "network: enabled\n  capabilities: [github.issue-view]")
            for adapter, body, diagnostic in (
                ("claude", declared.replace("network: enabled", "network: disabled"), "network=disabled"),
                ("claude", declared.replace("github.issue-view", "github.unknown"), "cannot enforce capability github.unknown"),
                ("codex", declared, "cannot enforce capability github.issue-view"),
                ("claude", declared.replace("workspace: read-only", "workspace: read-write"), "cannot enforce capability github.issue-view"),
                ("claude", declared.replace("inputs: {}", "  deny-capabilities: [github.issue-view]\ninputs: {}"), "explicitly denied"),
                ("claude", declared.replace("[github.issue-view]", "github.issue-view"), "list of unique capability names"),
                ("claude", declared.replace("[github.issue-view]", "[github.issue-view, github.issue-view]"), "list of unique capability names"),
            ):
                with self.subTest(adapter=adapter, diagnostic=diagnostic):
                    skill.write_text(body)
                    result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", adapter)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertEqual("", result.stdout)
            skill.write_text(declared)
            data = yaml.safe_load(profile.read_text())
            data["resources"]["network"] = "disabled"
            profile.write_text(yaml.safe_dump(data))
            result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "claude")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("network=disabled", result.stderr)

    def test_native_ceilings_and_denies_cannot_be_overridden(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, "claude")
            self.add_command(root)
            profile = root / ".ai-evo-prj/skills/config/effort-profiles/abc-default.yaml"
            data = yaml.safe_load(profile.read_text())
            data["resources"]["network"] = "auto"
            profile.write_text(yaml.safe_dump(data))
            skill = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
            skill.write_text(fixtures.VALID_COMMAND.replace("network: disabled",
                "network: enabled\n  capabilities: [github.issue-view]\n  deny-capabilities: [github.repo-view]"))
            engine = root / "engine"
            for directory in ("adapters", "schemas"):
                shutil.copytree(fixtures.ENGINE / directory, engine / directory)
            (root / ".ai-evo").unlink()
            (root / ".ai-evo").symlink_to(engine, target_is_directory=True)
            path = engine / "adapters/claude.yaml"
            adapter = yaml.safe_load(path.read_text())
            for native, success in (
                ([], True),
                (["--allowedTools", "Read,Bash"], True),
                (["--allowedTools", "Read"], False),
                (["--tools", "Read"], False),
                (["--dangerously-skip-permissions"], False),
                (["--mcp-config", "untrusted.json"], False),
                (["--disallowedTools", "Bash"], False),
                (["--disallowedTools", "Bash(.ai-evo/bin/ai-evo-github-read *)"], False),
                (["--disallowedTools", "Bash(.ai-evo/bin/ai-evo-github-read issue-view 12540)"], False),
                (["--disallowedTools", "Bash(*issue-view*)"], False),
            ):
                for layer in ("invocation", "session"):
                    with self.subTest(native=native, layer=layer):
                        adapter["invocation"]["command"] = ["claude", "-p"] + (native if layer == "invocation" else [])
                        adapter["session-translation"] = {reuse: native if layer == "session" else []
                            for reuse in ("never", "correction-only", "always")}
                        path.write_text(yaml.safe_dump(adapter))
                        result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "claude")
                        self.assertEqual(success, result.returncode == 0, result.stderr)
                        if success:
                            actual = options(json.loads(result.stdout)["application"]["cli_arguments"])
                            self.assertIn("Bash(.ai-evo/bin/ai-evo-github-read repo-view)", actual["--disallowedTools"])
                            self.assertIn("--strict-mcp-config", actual)
                        else:
                            self.assertIn("capability github.issue-view", result.stderr)
                            self.assertEqual("", result.stdout)

            skill.write_text(fixtures.VALID_COMMAND.replace("network: disabled",
                "network: enabled\n  deny-capabilities: [github.issue-view]"))
            adapter["session-translation"] = {reuse: [] for reuse in ("never", "correction-only", "always")}
            for bypass in (False, True):
                adapter["invocation"]["command"] = ["claude", "-p"] + (["--dangerously-skip-permissions"] if bypass else [])
                path.write_text(yaml.safe_dump(adapter))
                result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "claude")
                self.assertEqual(not bypass, result.returncode == 0, result.stderr)
                if bypass:
                    self.assertIn("capability github.issue-view", result.stderr)
                else:
                    actual = options(json.loads(result.stdout)["application"]["cli_arguments"])
                    self.assertIn("Bash(.ai-evo/bin/ai-evo-github-read issue-view *)", actual["--disallowedTools"])
                    self.assertNotIn("github-read", actual["--allowedTools"])


if __name__ == "__main__":
    unittest.main()
