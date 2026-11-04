from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/acme"
SCRIPT = EXAMPLE / "scripts/acme-supervisor-github-issue-workflow"
CONFIG_SCHEMA = json.loads((EXAMPLE / "supervisors/schemas/config.schema.json").read_text(encoding="utf-8"))
PROFILE_SCHEMA = json.loads((EXAMPLE / "supervisors/schemas/profile.schema.json").read_text(encoding="utf-8"))


class AcmeWorkflowSupervisorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        (self.workspace / ".ai-evo").mkdir()
        (self.workspace / ".ai-evo-work").mkdir()

    def invoke(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *arguments], cwd=self.workspace, capture_output=True, text=True,
        )

    def test_configuration_and_profiles_match_schemas(self) -> None:
        import yaml

        config = yaml.safe_load((EXAMPLE / "supervisors/config.yaml").read_text(encoding="utf-8"))
        jsonschema.validate(config, CONFIG_SCHEMA)
        for profile_name in ("supervised-local", "supervised-draft-prs"):
            profile = yaml.safe_load((
                EXAMPLE / f"supervisors/profiles/{profile_name}.yaml"
            ).read_text(encoding="utf-8"))
            jsonschema.validate(profile, PROFILE_SCHEMA)
            validated = self.invoke("validate", "--profile", profile_name)
            self.assertEqual(0, validated.returncode, validated.stderr)
            self.assertEqual("valid", json.loads(validated.stdout)["status"])

    def test_assignment_is_exclusive_and_resume_gets_new_run(self) -> None:
        first = self.invoke(
            "claim", "--issue", "321", "--profile", "supervised-local", "--owner", "codex",
        )
        self.assertEqual(0, first.returncode, first.stderr)
        assignment = json.loads(first.stdout)
        self.assertEqual("run-001", assignment["assignment_id"])

        conflict = self.invoke(
            "claim", "--issue", "321", "--profile", "supervised-local", "--owner", "other",
        )
        self.assertNotEqual(0, conflict.returncode)

        released = self.invoke(
            "release", "--issue", "321", "--owner", "codex",
            "--assignment-id", "run-001", "--reason", "handoff",
        )
        self.assertEqual(0, released.returncode, released.stderr)
        resumed = self.invoke(
            "claim", "--issue", "321", "--profile", "supervised-local", "--owner", "other",
        )
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertEqual("run-002", json.loads(resumed.stdout)["assignment_id"])

    def test_local_profile_disables_publication(self) -> None:
        report_path = self.workspace / "report.json"
        report_path.write_text(json.dumps({
            "schema_version": 1,
            "status": "ready",
            "issue": 321,
            "current_session": "issue-321/attempt-01/03-breakdown-attempt-01",
            "recommended_recipe": "acme-recipe-04-implement-github-issue",
            "worklog_session_name": "issue-321/attempt-01/04-implement-attempt-01",
            "resolved_inputs": {
                "issue": "321", "base_branch": "main",
                "worklog_session_name": "issue-321/attempt-01/04-implement-attempt-01",
                "worklog_session_input": '{"issue":"321"}',
            },
            "missing_inputs": [],
            "suggested_invocation": None,
            "reason": "implementation ready",
        }), encoding="utf-8")

        decided = self.invoke(
            "decide", "--issue", "321", "--profile", "supervised-local",
            "--report", str(report_path),
        )

        self.assertEqual(0, decided.returncode, decided.stderr)
        decision = json.loads(decided.stdout)
        self.assertEqual("execute-recipe", decision["action"])
        self.assertEqual("false", decision["inputs"]["publish_branch"])
        self.assertNotIn("publication_authorized", decision["inputs"])

    def test_summary_rejects_review_entry_without_immutable_digests(self) -> None:
        session = self.workspace / ".ai-evo-work/issue-321/attempt-01/05-review-attempt-01"
        session.mkdir(parents=True)
        (session / "001-verify.json").write_text(json.dumps({
            "outcome": "succeeded",
            "output": json.dumps({"status": "verified", "commit": {"oid": "a" * 40}}),
        }), encoding="utf-8")
        (session / "session.json").write_text(json.dumps({
            "schema_version": 1,
            "session_name": "issue-321/attempt-01/05-review-attempt-01",
            "recipe_name": "acme-recipe-05-review-github-issue",
            "status": "completed",
            "entries": [{
                "step_name": "verify_layer", "outcome": "succeeded", "file": "001-verify.json",
            }],
        }), encoding="utf-8")

        result = self.invoke("summarize", "--issue", "321", "--profile", "supervised-local")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("has no valid sha256", result.stderr)


if __name__ == "__main__":
    unittest.main()
