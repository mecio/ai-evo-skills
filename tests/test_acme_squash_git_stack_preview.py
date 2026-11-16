from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples/acme/scripts/acme-squash-git-stack-preview"
SCHEMA = json.loads((
    ROOT / "examples/acme/catalog/commands/acme-cmd-squash-git-stack-preview/references/output.schema.json"
).read_text(encoding="utf-8"))


class SquashGitStackPreviewTest(unittest.TestCase):
    issue = 12822

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.command("git", "init", "-q", "-b", "main")
        self.command("git", "config", "user.name", "Preview Test")
        self.command("git", "config", "user.email", "preview@example.invalid")
        self.command("git", "remote", "add", "origin", str(self.workspace / "unused-origin.git"))
        (self.workspace / ".ai-evo").mkdir()
        (self.workspace / ".gitignore").write_text(".ai-evo/\n.ai-evo-work/\n", encoding="utf-8")
        (self.workspace / "base.txt").write_text("base\n", encoding="utf-8")
        self.command("git", "add", "base.txt", ".gitignore")
        self.command("git", "commit", "-qm", "initial")
        self.base_oid = self.git_text("rev-parse", "HEAD")

        self.layer0 = "feature/stack/00_base"
        self.layer1 = "feature/stack/01_child"
        self.command("git", "switch", "-qc", self.layer0)
        (self.workspace / "layer0.txt").write_text("layer zero\n", encoding="utf-8")
        self.command("git", "add", "layer0.txt")
        self.command("git", "commit", "-qm", f"#{self.issue} layer zero")
        self.command("git", "switch", "-qc", self.layer1)
        (self.workspace / "layer1.txt").write_text("layer one\n", encoding="utf-8")
        self.command("git", "add", "layer1.txt")
        self.command("git", "commit", "-qm", f"#{self.issue} layer one")
        self.source_oid = self.git_text("rev-parse", "HEAD")
        self.write_worklog()
        self.write_workspace_manifest()

    def command(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            arguments, cwd=self.workspace, text=True, capture_output=True, check=check,
        )

    def git_text(self, *arguments: str) -> str:
        return self.command("git", *arguments).stdout.strip()

    def write_worklog(self) -> None:
        for layer, branch in (("L0", self.layer0), ("L1", self.layer1)):
            name = f"issue-{self.issue}/attempt-01/layers/{layer}/04-implement-attempt-01"
            directory = self.workspace / ".ai-evo-work" / name
            directory.mkdir(parents=True)
            (directory / "session.json").write_text(json.dumps({
                "session_name": name,
                "session_slug": name,
                "recipe_name": "acme-recipe-04-implement-github-issue",
                "session_input": {"branch": branch},
                "status": "completed",
                "entries": [],
            }), encoding="utf-8")

    def write_workspace_manifest(self) -> None:
        common = Path(self.git_text("rev-parse", "--path-format=absolute", "--git-common-dir"))
        path = common / "acme-issues" / f"issue-{self.issue}" / "attempt-01" / "workspace.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schema_version": 1,
            "issue": self.issue,
            "workflow_attempt": 1,
            "status": "ready",
            "workspace_mode": "current",
            "coordinator_root": str(self.workspace),
            "working_directory": str(self.workspace),
        }), encoding="utf-8")

    def invoke(self, **overrides: object) -> subprocess.CompletedProcess[str]:
        request: dict[str, object] = {"issue": self.issue}
        request.update(overrides)
        return self.command(str(SCRIPT), "create", json.dumps(request), check=False)

    def branch_exists(self, branch: str) -> bool:
        return self.command(
            "git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False,
        ).returncode == 0

    def test_creates_one_commit_preview_of_two_layer_stack_without_touching_checkout(self) -> None:
        before_branch = self.git_text("branch", "--show-current")
        before_head = self.git_text("rev-parse", "HEAD")
        before_status = self.command("git", "status", "--porcelain=v1", "-z").stdout

        result = self.invoke()

        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        jsonschema.validate(output, SCHEMA)
        preview = f"tmp/{self.issue}-squash"
        self.assertEqual(preview, output["preview_branch"])
        self.assertEqual("main", output["base_branch"])
        self.assertEqual(self.base_oid, output["base_oid"])
        self.assertEqual(self.layer1, output["source_branch"])
        self.assertEqual(self.source_oid, output["source_oid"])
        self.assertTrue(output["tree_identical"])
        self.assertEqual(2, output["files_changed"])
        self.assertEqual(2, output["insertions"])
        self.assertEqual(0, output["deletions"])
        self.assertEqual(1, int(self.git_text("rev-list", "--count", f"{self.base_oid}..{preview}")))
        self.assertEqual(0, self.command("git", "diff", "--quiet", self.layer1, preview, check=False).returncode)
        self.assertEqual("", self.git_text("for-each-ref", "--format=%(upstream:short)", f"refs/heads/{preview}"))
        message = self.git_text("log", "-1", "--format=%B", preview)
        self.assertTrue(message.startswith(f"#{self.issue} squash temporaneo dello stack"))
        self.assertNotIn("Co-Authored-By", message)
        self.assertEqual(before_branch, self.git_text("branch", "--show-current"))
        self.assertEqual(before_head, self.git_text("rev-parse", "HEAD"))
        self.assertEqual(before_status, self.command("git", "status", "--porcelain=v1", "-z").stdout)

    def test_refuses_dirty_worktree_without_creating_preview(self) -> None:
        (self.workspace / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        result = self.invoke()

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worktree must be clean", result.stderr)
        self.assertFalse(self.branch_exists(f"tmp/{self.issue}-squash"))

    def test_refuses_existing_preview_branch_without_replace(self) -> None:
        preview = f"tmp/{self.issue}-squash"
        self.command("git", "branch", preview, "main")
        old_oid = self.git_text("rev-parse", preview)

        result = self.invoke()

        self.assertNotEqual(0, result.returncode)
        self.assertIn("preview branch already exists", result.stderr)
        self.assertEqual(old_oid, self.git_text("rev-parse", preview))

    def test_refuses_replace_existing_for_a_non_preview_commit(self) -> None:
        preview = f"tmp/{self.issue}-squash"
        self.command("git", "branch", preview, "main")
        old_oid = self.git_text("rev-parse", preview)

        result = self.invoke(replace_existing=True)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("is not a squash preview", result.stderr)
        self.assertEqual(old_oid, self.git_text("rev-parse", preview))

    def test_replace_existing_updates_only_a_preview_of_the_same_issue(self) -> None:
        preview = f"tmp/{self.issue}-squash"
        first = self.invoke()
        self.assertEqual(0, first.returncode, first.stderr)
        first_oid = self.git_text("rev-parse", preview)
        (self.workspace / "later.txt").write_text("later\n", encoding="utf-8")
        self.command("git", "add", "later.txt")
        self.command("git", "commit", "-qm", f"#{self.issue} later change")

        result = self.invoke(replace_existing=True)

        self.assertEqual(0, result.returncode, result.stderr)
        replacement = json.loads(result.stdout)
        self.assertEqual(self.layer1, replacement["source_branch"])
        self.assertNotEqual(first_oid, self.git_text("rev-parse", preview))
        self.assertEqual(0, self.command("git", "diff", "--quiet", self.layer1, preview, check=False).returncode)
        self.assertEqual("", self.git_text("for-each-ref", "--format=%(upstream:short)", f"refs/heads/{preview}"))

    def test_can_preview_an_explicit_intermediate_layer(self) -> None:
        preview = f"tmp/{self.issue}-l0-squash"

        result = self.invoke(branch=self.layer0, preview_branch=preview)

        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(self.layer0, output["source_branch"])
        self.assertEqual(0, self.command("git", "diff", "--quiet", self.layer0, preview, check=False).returncode)

    def test_installed_script_reads_configuration_from_skills_config(self) -> None:
        project = self.workspace / ".ai-evo-prj"
        shutil.copytree(ROOT / "examples/acme/scripts", project / "scripts")
        shutil.copytree(ROOT / "examples/acme/config", project / "skills/config")
        exclude = self.workspace / ".git/info/exclude"
        exclude.write_text(exclude.read_text(encoding="utf-8") + ".ai-evo-prj/\n", encoding="utf-8")

        result = self.command(
            str(project / "scripts/acme-squash-git-stack-preview"), "create",
            json.dumps({"issue": self.issue, "branch": self.layer1}), check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        jsonschema.validate(json.loads(result.stdout), SCHEMA)


if __name__ == "__main__":
    unittest.main()
