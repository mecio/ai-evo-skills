from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/acme"
SCRIPT = EXAMPLE / "scripts/acme-report-github-issue-workflow"


class AcmeWorkflowRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        (self.workspace / ".ai-evo").mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.workspace)], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.email", "test@example.invalid"], check=True)
        (self.workspace / "README").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "README"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "initial"], check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def session(self, name: str, recipe: str, *, status: str = "completed",
                entries: list[object] | None = None, session_input: object | None = None) -> Path:
        directory = self.workspace / ".ai-evo-work" / name
        directory.mkdir(parents=True)
        (directory / "session.json").write_text(json.dumps({
            "session_name": name,
            "session_slug": name,
            "recipe_name": recipe,
            "session_input": session_input,
            "status": status,
            "entries": [] if entries is None else entries,
        }), encoding="utf-8")
        return directory

    def invoke(self, requested_recipe: str | None = None,
               correction_instructions: str = "") -> dict[str, object]:
        arguments = [str(SCRIPT), "report", "--issue", "12553"]
        if requested_recipe:
            arguments.extend(["--requested-recipe", requested_recipe])
        if correction_instructions:
            arguments.extend(["--correction-instructions", correction_instructions])
        result = subprocess.run(arguments, cwd=self.workspace, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def stack_layer(self, branch: str, parent: str = "main") -> str:
        subprocess.run(["git", "-C", str(self.workspace), "checkout", "-qb", branch, parent], check=True)
        (self.workspace / "implementation.txt").write_text("done\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "implementation.txt"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "#12553 implement layer"], check=True)
        return subprocess.check_output(
            ["git", "-C", str(self.workspace), "rev-parse", branch], text=True,
        ).strip()

    def write_stack_metadata(self, branch: str) -> None:
        git_dir = subprocess.check_output(
            ["git", "-C", str(self.workspace), "rev-parse", "--git-dir"], text=True,
        ).strip()
        (self.workspace / git_dir / "gh-stack").write_text(json.dumps({
            "stacks": [{"trunk": {"branch": "main"}, "branches": [{"branch": branch}]}],
        }), encoding="utf-8")

    def implementation_checkpoint(self, name: str, branch: str, *, status: str = "completed",
                                  correction: bool = False,
                                  session_input: object | None = None) -> Path:
        step = "correct_implementation" if correction else "implement_issue"
        recipe = ("acme-recipe-04-implement-github-issue-correction" if correction
                  else "acme-recipe-04-implement-github-issue")
        directory = self.session(
            name, recipe, status=status,
            entries=[{"step_name": step, "outcome": "succeeded", "file": "001-implement.json"}],
            session_input=session_input or {"developer_instructions": "Vincolo originale"},
        )
        oid = subprocess.check_output(
            ["git", "-C", str(self.workspace), "rev-parse", branch], text=True,
        ).strip()
        report = {
            "branch": branch, "parent_branch": "main", "base_branch": "main", "sequence": 0,
            "commits": [{"sha": oid, "subject": "#12553 implement layer"}],
            "tests": [], "open_decisions": [], "limits": [], "report": "implementazione",
        }
        (directory / "001-implement.json").write_text(json.dumps({
            "outcome": "succeeded", "output": json.dumps(report),
        }), encoding="utf-8")
        return directory

    def publish_checkpoint(self, directory: Path, branch: str) -> str:
        oid = subprocess.check_output(
            ["git", "-C", str(self.workspace), "rev-parse", branch], text=True,
        ).strip()
        session_path = directory / "session.json"
        session = json.loads(session_path.read_text(encoding="utf-8"))
        session["status"] = "completed"
        session["entries"].append({
            "step_name": "publish_branch", "outcome": "succeeded", "file": "002-publish.json",
        })
        session_path.write_text(json.dumps(session), encoding="utf-8")
        (directory / "002-publish.json").write_text(json.dumps({"output": json.dumps({
            "branch": branch, "parent_branch": "main", "remote": "origin", "remote_oid": oid,
        })}), encoding="utf-8")
        return oid

    def completed_review(self, name: str, branch: str, oid: str,
                         previous_session: str,
                         implementation_instructions: str = "Vincolo originale") -> Path:
        directory = self.session(
            name, "acme-recipe-05-review-github-issue",
            entries=[{"step_name": "verify_layer", "outcome": "succeeded", "file": "001-verify.json"}],
            session_input={
                "previous_session": previous_session,
                "implementation_instructions": implementation_instructions,
            },
        )
        verification = {
            "status": "verified", "commit": {"oid": oid},
            "stack_state": {
                "current_branch": branch, "trunk": "main",
                "branches": [{"name": branch, "parent": "main"}],
            },
        }
        (directory / "001-verify.json").write_text(json.dumps({
            "output": json.dumps(verification),
        }), encoding="utf-8")
        (directory / "issue-12553-review.md").write_text("# Review con finding F1\n", encoding="utf-8")
        return directory

    def prepare_reviewed_single(self) -> tuple[str, Path, str]:
        breakdown = self.session(
            "issue-12553/attempt-01/03-breakdown-attempt-01",
            "acme-recipe-03-breakdown-github-issue",
        )
        (breakdown / "issue-12553-breakdown.json").write_text('{"mode":"single"}\n', encoding="utf-8")
        branch = "feature/12553/implementation"
        self.stack_layer(branch)
        self.write_stack_metadata(branch)
        implementation = self.implementation_checkpoint(
            "issue-12553/attempt-01/04-implement-attempt-01", branch,
        )
        oid = self.publish_checkpoint(implementation, branch)
        review = self.completed_review(
            "issue-12553/attempt-01/05-review-attempt-01", branch, oid,
            "issue-12553/attempt-01/04-implement-attempt-01",
        )
        return branch, review, oid

    def test_completed_review_opens_additive_correction_with_lineage(self) -> None:
        _, review, oid = self.prepare_reviewed_single()

        report = self.invoke(
            "acme-recipe-04-implement-github-issue-correction",
            "Correggi il finding F1.",
        )

        self.assertEqual("acme-recipe-04-implement-github-issue-correction", report["recommended_recipe"])
        self.assertEqual("issue-12553/attempt-01/04-correction-attempt-01", report["worklog_session_name"])
        lineage = json.loads(report["resolved_inputs"]["worklog_session_input"])
        self.assertEqual(str(review / "issue-12553-review.md"), lineage["source_review"])
        implementation = json.loads(report["resolved_inputs"]["implementation_report"])
        self.assertEqual(oid, implementation["commits"][-1]["sha"])

    def test_published_correction_reopens_review_on_new_oid(self) -> None:
        branch, _, _ = self.prepare_reviewed_single()
        requested = self.invoke(
            "acme-recipe-04-implement-github-issue-correction",
            "Correggi il finding F1.",
        )
        (self.workspace / "correction.txt").write_text("fix\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "correction.txt"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "#12553 fix finding"], check=True)
        correction = self.implementation_checkpoint(
            "issue-12553/attempt-01/04-correction-attempt-01", branch, correction=True,
            session_input=json.loads(requested["resolved_inputs"]["worklog_session_input"]),
        )
        corrected_oid = self.publish_checkpoint(correction, branch)

        report = self.invoke()

        self.assertEqual("acme-recipe-05-review-github-issue", report["recommended_recipe"])
        self.assertEqual("issue-12553/attempt-01/05-review-attempt-02", report["worklog_session_name"])
        self.assertIn("05-review-attempt-01", report["resolved_inputs"]["previous_review"])
        self.assertEqual(
            "Vincolo originale\n\nCorreggi il finding F1.",
            report["resolved_inputs"]["implementation_instructions"],
        )
        self.assertEqual(corrected_oid, subprocess.check_output(
            ["git", "-C", str(self.workspace), "rev-parse", branch], text=True,
        ).strip())

    def test_second_reviewed_correction_preserves_all_prior_instructions(self) -> None:
        branch, _, _ = self.prepare_reviewed_single()
        first = self.invoke(
            "acme-recipe-04-implement-github-issue-correction",
            "Correggi il finding F1.",
        )
        (self.workspace / "correction.txt").write_text("fix\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "correction.txt"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "#12553 fix finding"], check=True)
        correction = self.implementation_checkpoint(
            "issue-12553/attempt-01/04-correction-attempt-01", branch, correction=True,
            session_input=json.loads(first["resolved_inputs"]["worklog_session_input"]),
        )
        corrected_oid = self.publish_checkpoint(correction, branch)
        review_request = self.invoke()
        cumulative = review_request["resolved_inputs"]["implementation_instructions"]
        self.completed_review(
            "issue-12553/attempt-01/05-review-attempt-02", branch, corrected_oid,
            "issue-12553/attempt-01/04-correction-attempt-01", cumulative,
        )

        second = self.invoke(
            "acme-recipe-04-implement-github-issue-correction",
            "Correggi anche il finding F2.",
        )

        self.assertEqual("Vincolo originale", second["resolved_inputs"]["developer_instructions"])
        lineage = json.loads(second["resolved_inputs"]["worklog_session_input"])
        self.assertEqual(
            "Vincolo originale\n\nCorreggi il finding F1.\n\nCorreggi anche il finding F2.",
            lineage["implementation_instructions"],
        )


if __name__ == "__main__":
    unittest.main()
