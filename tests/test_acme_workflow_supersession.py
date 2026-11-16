from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest import mock

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/acme"
REPORT = EXAMPLE / "scripts/acme-report-github-issue-workflow"
ABANDON = EXAMPLE / "scripts/acme-abandon-github-issue-session"
ABANDON_SCHEMA = json.loads((
    EXAMPLE / "catalog/commands/acme-cmd-abandon-github-issue-session/references/output.schema.json"
).read_text(encoding="utf-8"))
REPORT_SCHEMA = json.loads((
    EXAMPLE / "catalog/commands/acme-cmd-report-github-issue-workflow/references/output.schema.json"
).read_text(encoding="utf-8"))


class AcmeWorkflowSupersessionTest(unittest.TestCase):
    issue = 12553

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.workspace)], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.email", "test@example.invalid"], check=True)
        (self.workspace / ".ai-evo").mkdir()
        (self.workspace / "README").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "README"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "initial"], check=True)

    def session(self, name: str, *, status: str = "active",
                entries: list[dict[str, object]] | None = None) -> Path:
        directory = self.workspace / ".ai-evo-work" / name
        directory.mkdir(parents=True)
        session = {
            "schema_version": 1,
            "session_name": name,
            "session_slug": name,
            "recipe_name": "acme-recipe-04-implement-github-issue",
            "session_input": {"issue": str(self.issue)},
            "created_at": "2026-11-16T10:00:00.000000Z",
            "updated_at": "2026-11-16T10:00:00.000000Z",
            "status": status,
            "entries": entries or [],
        }
        (directory / "session.json").write_text(json.dumps(session), encoding="utf-8")
        (directory / "context.md").write_text(
            f"# Session `{name}`\n\n- Status: `{status}`\n- Updated: `2026-11-16T10:00:00.000000Z`\n",
            encoding="utf-8",
        )
        return directory

    def load_report(self, name: str):
        loader = SourceFileLoader(name, str(REPORT))
        spec = spec_from_loader(loader.name, loader)
        assert spec is not None
        module = module_from_spec(spec)
        sys.path.insert(0, str(REPORT.parent))
        try:
            loader.exec_module(module)
        finally:
            sys.path.pop(0)
        return module

    def test_abandon_is_separate_terminal_operation(self) -> None:
        name = f"issue-{self.issue}/attempt-01/04-implement-attempt-01"
        directory = self.session(name)
        result = subprocess.run([
            str(ABANDON), "abandon", json.dumps({
                "issue": self.issue, "session_name": name, "reason": "Piano sostituito",
            }),
        ], cwd=self.workspace, capture_output=True, text=True)

        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        jsonschema.validate(output, ABANDON_SCHEMA)
        saved = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        self.assertEqual("abandoned", saved["status"])
        self.assertEqual("Piano sostituito", saved["abandoned_reason"])
        self.assertEqual(saved["abandoned_at"], saved["updated_at"])
        self.assertIn("Status: `abandoned`", (directory / "context.md").read_text(encoding="utf-8"))

    def test_abandon_rejects_a_succeeded_remote_step(self) -> None:
        name = f"issue-{self.issue}/attempt-01/04-implement-attempt-01"
        self.session(name, entries=[{"step_name": "publish_branch", "outcome": "succeeded"}])
        result = subprocess.run([
            str(ABANDON), "abandon", json.dumps({
                "issue": self.issue, "session_name": name, "reason": "Piano sostituito",
            }),
        ], cwd=self.workspace, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("remote step publish_branch succeeded", result.stderr)

    def test_abandon_rejects_an_unindexed_remote_record(self) -> None:
        name = f"issue-{self.issue}/attempt-01/04-implement-attempt-01"
        directory = self.session(name)
        (directory / "001-publish-branch-acme-cmd-push-attempt-01.json").write_text(json.dumps({
            "schema_version": 1,
            "session_slug": name,
            "recipe_name": "acme-recipe-04-implement-github-issue",
            "step_name": "publish_branch",
            "outcome": "succeeded",
        }), encoding="utf-8")

        result = subprocess.run([
            str(ABANDON), "abandon", json.dumps({
                "issue": self.issue, "session_name": name, "reason": "Piano sostituito",
            }),
        ], cwd=self.workspace, capture_output=True, text=True)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("remote step publish_branch succeeded", result.stderr)

    def test_abandoned_session_does_not_supersede_a_completed_checkpoint(self) -> None:
        module = self.load_report("acme_report_abandoned_chronology_test")
        completed = {
            "path": self.workspace / "completed", "phase": "03", "phase_attempt": 1,
            "action": "breakdown", "layer_id": None, "workflow_attempt": 1,
            "session": {"status": "completed", "session_name": "completed",
                        "updated_at": "2026-11-16T10:00:00Z"},
        }
        abandoned = {
            "path": self.workspace / "abandoned", "phase": "04", "phase_attempt": 1,
            "action": "implement", "layer_id": None, "workflow_attempt": 1,
            "session": {"status": "abandoned", "session_name": "abandoned",
                        "updated_at": "2026-11-16T11:00:00Z"},
        }

        self.assertIs(completed, module.latest_phase([completed, abandoned]))
        abandoned_layer = {**abandoned, "layer_id": "L0"}
        self.assertIsNone(module.latest_layer_session([abandoned_layer], "L0", "04"))
        self.assertEqual(2, module.next_layer_phase_attempt([abandoned_layer], "L0", "04"))

    def test_child_rebase_recommendation_matches_report_schema(self) -> None:
        module = self.load_report("acme_report_child_rebase_schema_test")
        current = {"session": {"session_name": "correction"}}
        layer_session = {"session": {"status": "completed"}}
        with (mock.patch.object(module, "latest_layer_session", return_value=layer_session),
              mock.patch.object(module, "layer_branch", return_value=("child", None, [])),
              mock.patch.object(module.subprocess, "run",
                                return_value=subprocess.CompletedProcess([], 1, "", ""))):
            result = module.stale_stacked_children(
                self.issue, current, self.workspace, "parent",
                [{"id": "L0"}, {"id": "L1"}], 0, [],
            )

        self.assertIsNotNone(result)
        jsonschema.validate(result, REPORT_SCHEMA)
        self.assertEqual("acme-recipe-rebase-and-republish-github-stack", result["recommended_recipe"])

    def test_published_attempt_requires_and_records_explicit_supersession(self) -> None:
        name = f"issue-{self.issue}/attempt-01/04-implement-attempt-01"
        directory = self.session(name, status="completed", entries=[{
            "step_name": "publish_branch", "outcome": "succeeded", "file": "001-publish.json",
        }])
        oid = subprocess.check_output(
            ["git", "-C", str(self.workspace), "rev-parse", "HEAD"], text=True,
        ).strip()
        (directory / "001-publish.json").write_text(json.dumps({"output": json.dumps({
            "branch": "feature/12553", "remote_oid": oid,
        })}), encoding="utf-8")
        base = [
            str(REPORT), "report", "--issue", str(self.issue),
            "--requested-recipe", "acme-recipe-01-refine-github-issue",
            "--new-workflow-attempt", "true", "--reason", "Cambio piano",
        ]
        rejected = subprocess.run(base, cwd=self.workspace, capture_output=True, text=True, check=True)
        self.assertEqual("manual-assessment-required", json.loads(rejected.stdout)["status"])

        accepted = subprocess.run(
            [*base, "--supersede-published", "true"], cwd=self.workspace,
            capture_output=True, text=True, check=True,
        )
        report = json.loads(accepted.stdout)
        self.assertEqual("ready", report["status"])
        session_input = json.loads(report["resolved_inputs"]["worklog_session_input"])
        self.assertTrue(session_input["supersede_published"])
        index = json.loads((self.workspace / ".ai-evo-work" / f"issue-{self.issue}" / "index.json").read_text())
        self.assertEqual(
            [{"name": "feature/12553", "remote_oid": oid}],
            index["attempts"]["attempt-01"]["published_branches"],
        )

    def test_recipe_inputs_forward_supersede_published(self) -> None:
        for phase in ("01-refine-github-issue", "02-analyze-github-issue-code"):
            recipe = (EXAMPLE / "catalog/recipes" / f"acme-recipe-{phase}" / "recipe.yaml").read_text()
            self.assertIn("supersede_published:", recipe)
            self.assertIn('${{ inputs.supersede_published }}', recipe)

    def test_submit_oid_guard_and_layer_chronology(self) -> None:
        module = self.load_report("acme_report_for_supersession_test")
        publication_session = {
            "path": self.workspace,
            "phase": "07", "phase_attempt": 1, "layer_id": None,
            "session": {"session_name": "phase-07", "status": "completed",
                        "created_at": "2026-11-16T10:00:00Z"},
        }
        later_rebase = {
            "path": self.workspace,
            "phase": "04r", "phase_attempt": 1, "layer_id": "L0",
            "session": {"session_name": "layer-04r", "status": "completed",
                        "created_at": "2026-11-16T11:00:00Z"},
        }
        later_correction = {
            **later_rebase,
            "phase": "04", "action": "correction",
            "session": {"session_name": "layer-correction", "status": "completed",
                        "created_at": "2026-11-16T12:00:00Z"},
        }
        self.assertTrue(module.superseded_by_layer_sessions(publication_session, [publication_session, later_rebase]))
        submit = {**publication_session, "phase": "08"}
        self.assertFalse(module.superseded_by_layer_sessions(submit, [submit, later_rebase]))
        self.assertTrue(module.superseded_by_layer_sessions(submit, [submit, later_correction]))

        old_oid, new_oid = "a" * 40, "b" * 40
        problem = module.submit_verification_problem(
            self.issue, publication_session,
            {"branches": [{"branch": "feature/12553", "remote_oid": old_oid}]},
            json.dumps({
                "commit": {"oid": new_oid},
                "stack_state": {"current_branch": "feature/12553"},
            }),
            self.workspace, [publication_session],
        )
        self.assertIsInstance(problem, str)
        self.assertIn(old_oid, problem)
        self.assertIn(new_oid, problem)


if __name__ == "__main__":
    unittest.main()
