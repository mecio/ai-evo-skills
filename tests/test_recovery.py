from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest

import test_recipe_conditions as fixtures
from ai_evo_skills.execution import ExecutionError
from ai_evo_skills.recovery import recover_prefix, fingerprint


def evidence(source, target):
    return {"source_sha256": fingerprint(source), "target_sha256": fingerprint(target), "checks": [
        {"step": result["step"], "output_sha256": fingerprint(result["output"]), "valid": True,
         "checked_at": datetime.now(timezone.utc).isoformat(), "reason": "Fixture dependencies verified",
         "source_dependencies": {"head": "fixture-head", "issue": "fixture-issue"},
         "current_dependencies": {"head": "fixture-head", "issue": "fixture-issue"}}
        for result in source["results"] if result["status"] == "succeeded"]}


class RecoveryTest(unittest.TestCase):
    def fixture(self):
        return fixtures.RecipeConditionsTest()

    def source(self, plan):
        return {"plan": plan, "results": [
            {"step": "detect", "status": "succeeded", "output": "php83"},
            {"step": "legacy", "status": "succeeded", "output": "passed"},
            {"step": "unit", "status": "failed", "exit_code": 1}]}

    def test_array_output_is_revalidated_before_recovery(self):
        fixture = self.fixture()
        with fixture.project() as (root, path, data):
            plan = fixture.plan(root, path, data)
            plan['execution']['steps'][0]['application']['output_contract'] = {
                'format': 'json-array', 'schema': {'type': 'array', 'items': {'type': 'integer'}}}
            for output, expected in (('[1,2]', ['detect']), ('["invalid"]', [])):
                source = {'plan': plan, 'results': [
                    {'step': 'detect', 'status': 'succeeded', 'output': output},
                    {'step': 'legacy', 'status': 'failed', 'exit_code': 1}]}
                before = deepcopy(source)
                recovered, report = recover_prefix(source, plan, evidence(source, plan))
                self.assertEqual(expected, [r['step'] for r in recovered['results']])
                self.assertEqual('legacy' if expected else 'detect', report['next_step'])
                self.assertEqual(before, source)

    def test_prefix_stops_at_failure_or_first_invalid_dependency(self):
        fixture = self.fixture()
        with fixture.project() as (root, path, data):
            plan = fixture.plan(root, path, data)
            source = self.source(plan)
            original = deepcopy(source)
            checks = evidence(source, plan)
            state, report = recover_prefix(source, plan, checks)
            self.assertEqual(["detect", "legacy"], [r["step"] for r in state["results"]])
            self.assertEqual("unit", report["next_step"])
            checks["checks"][0]["current_dependencies"]["issue"] = "changed"
            state, report = recover_prefix(source, plan, checks)
            self.assertEqual([], state["results"])
            self.assertEqual("detect", report["next_step"])
            checks = evidence(source, plan)
            checks["checks"][1]["valid"] = False
            state, report = recover_prefix(source, plan, checks)
            self.assertEqual(["detect"], [r["step"] for r in state["results"]])
            self.assertEqual("legacy", report["next_step"])
            checks["checks"] = []
            self.assertEqual([], recover_prefix(source, plan, checks)[0]["results"])
            self.assertEqual(original, source)

    def test_changed_commands_and_tampered_evidence_cannot_be_reused(self):
        fixture = self.fixture()
        with fixture.project() as (root, path, data):
            plan = fixture.plan(root, path, data)
            source = self.source(plan)
            target = deepcopy(plan)
            target["execution"]["steps"][1]["handoff"]["skill_content"] += "\nNew instruction"
            state, report = recover_prefix(source, target, evidence(source, target))
            self.assertEqual(1, len(state["results"]))
            self.assertEqual("legacy", report["next_step"])
            checks = evidence(source, plan)
            checks["checks"][0]["output_sha256"] = "tampered"
            with self.assertRaises(ExecutionError):
                recover_prefix(source, plan, checks)
            checks = evidence(source, plan)
            checks["source_sha256"] = "tampered"
            with self.assertRaises(ExecutionError):
                recover_prefix(source, plan, checks)

    def test_cli_creates_new_state_and_preserves_source(self):
        fixture = self.fixture()
        with fixture.project() as (root, path, data):
            plan = fixture.plan(root, path, data)
            source = self.source(plan)
            old = root / "old"
            old.mkdir()
            source_path = old / "state.json"
            source_path.write_text(json.dumps(source))
            (root / "target.json").write_text(json.dumps(plan))
            (root / "checks.json").write_text(json.dumps(evidence(source, plan)))
            original = source_path.read_bytes()
            inspected = fixture.run_cli(root, "recipe", "recover", "--source-state", str(source_path),
                                        "--plan", str(root / "target.json"), "--inspect")
            self.assertEqual(0, inspected.returncode, inspected.stderr)
            self.assertEqual([], recover_prefix(source, plan, json.loads(inspected.stdout))[0]["results"])
            command = ("recipe", "recover", "--source-state", str(source_path), "--plan", str(root / "target.json"),
                       "--evidence", str(root / "checks.json"), "--output-dir", str(root / "new"))
            result = fixture.run_cli(root, *command)
            self.assertEqual(0, result.returncode, result.stderr)
            state = json.loads((root / "new/state.json").read_text())
            self.assertEqual(source["results"][:2], state["results"])
            self.assertEqual(original, source_path.read_bytes())
            self.assertNotEqual(0, fixture.run_cli(root, *command).returncode)
            self.assertEqual(original, source_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
