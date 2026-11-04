from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/acme"
HELPER = EXAMPLE / "scripts/acme-issue-workspace"
PREPARE_SCHEMA = json.loads((
    EXAMPLE / "catalog/commands/acme-cmd-prepare-github-issue-workspace/references/output.schema.json"
).read_text(encoding="utf-8"))
REPAIR_SCHEMA = json.loads((
    EXAMPLE / "catalog/commands/acme-cmd-repair-github-issue-workspace/references/output.schema.json"
).read_text(encoding="utf-8"))
CLENUP_SCHEMA = json.loads((
    EXAMPLE / "catalog/commands/acme-cmd-cleanup-github-issue-workspace/references/output.schema.json"
).read_text(encoding="utf-8"))


class AcmeIssueWorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.test")
        (self.root / "README").write_text("fixture\n", encoding="utf-8")
        self.git("add", "README")
        self.git("commit", "-qm", "initial")
        for relative in (".ai-evo", ".ai-evo-prj"):
            source = Path(self.temporary.name) / relative.removeprefix(".")
            source.mkdir()
            (self.root / relative).symlink_to(source, target_is_directory=True)
        (self.root / ".ai-evo-skills.yaml").write_text("version: '1.0'\n", encoding="utf-8")
        worklog = Path(self.temporary.name) / "worklog"
        worklog.mkdir()
        (self.root / ".ai-evo-work").symlink_to(worklog, target_is_directory=True)
        for relative in (".agents/skills", ".claude/skills"):
            directory = self.root / relative
            directory.mkdir(parents=True)
            (directory / "fixture").write_text("skill\n", encoding="utf-8")

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=self.root, check=True, capture_output=True, text=True,
        ).stdout.strip()

    def prepare(self, mode: str) -> subprocess.CompletedProcess[str]:
        request = {
            "issue": "321", "base_branch": "main", "workspace_mode": mode,
            "worklog_session_name": "issue-321/attempt-02/04-implement-attempt-01",
        }
        return subprocess.run(
            [str(HELPER), "prepare", json.dumps(request)], cwd=self.root,
            capture_output=True, text=True,
        )

    def test_current_assignment_is_idempotent(self) -> None:
        first = self.prepare("current")
        self.assertEqual(0, first.returncode, first.stderr)
        assignment = json.loads(first.stdout)
        jsonschema.validate(assignment, PREPARE_SCHEMA)
        self.assertEqual(str(self.root), assignment["working_directory"])
        self.assertEqual([], assignment["provision"]["linked_resources"])
        repeated = self.prepare("current")
        self.assertEqual(assignment, json.loads(repeated.stdout))

    def test_isolated_assignment_repair_and_cleanup(self) -> None:
        first = self.prepare("isolated")
        self.assertEqual(0, first.returncode, first.stderr)
        assignment = json.loads(first.stdout)
        jsonschema.validate(assignment, PREPARE_SCHEMA)
        worktree = Path(assignment["working_directory"])
        self.assertEqual(self.root / ".sub-worktrees/issues/issue-321/attempt-02", worktree)
        self.assertEqual("", subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=worktree, text=True,
        ).strip())
        self.assertEqual(assignment["base_oid"], subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=worktree, text=True,
        ).strip())
        for relative in assignment["provision"]["linked_resources"]:
            self.assertTrue((worktree / relative).is_symlink(), relative)
        self.assertEqual("", subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=worktree, text=True,
        ))

        (worktree / ".ai-evo").unlink()
        repair_request = {
            "issue": "321",
            "worklog_session_name": "issue-321/attempt-02/05-review-attempt-01",
        }
        repaired = subprocess.run(
            [str(HELPER), "repair", json.dumps(repair_request)], cwd=self.root,
            capture_output=True, text=True,
        )
        self.assertEqual(0, repaired.returncode, repaired.stderr)
        repair = json.loads(repaired.stdout)
        jsonschema.validate(repair, REPAIR_SCHEMA)
        self.assertTrue((worktree / ".ai-evo").is_symlink())

        cleanup_name = "issue-321/attempt-02/08-submit-attempt-01"
        submit = self.root / ".ai-evo-work" / cleanup_name
        submit.mkdir(parents=True)
        (submit / "session.json").write_text(json.dumps({
            "session_name": cleanup_name,
            "recipe_name": "acme-recipe-08-submit-github-stack",
            "status": "completed",
        }), encoding="utf-8")
        cleaned = subprocess.run(
            [str(HELPER), "cleanup", json.dumps({
                "issue": "321", "worklog_session_name": cleanup_name,
            })],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(0, cleaned.returncode, cleaned.stderr)
        cleanup = json.loads(cleaned.stdout)
        jsonschema.validate(cleanup, CLENUP_SCHEMA)
        self.assertFalse(worktree.exists())

    def test_concurrent_prepare_returns_one_assignment(self) -> None:
        request = json.dumps({
            "issue": "321", "base_branch": "main", "workspace_mode": "isolated",
            "worklog_session_name": "issue-321/attempt-02/04-implement-attempt-01",
        })
        command = [str(HELPER), "prepare", request]
        processes = [subprocess.Popen(
            command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) for _ in range(2)]
        results = [process.communicate(timeout=10) for process in processes]
        for process, (_, stderr) in zip(processes, results):
            self.assertEqual(0, process.returncode, stderr)
        self.assertEqual(json.loads(results[0][0]), json.loads(results[1][0]))


if __name__ == "__main__":
    unittest.main()
