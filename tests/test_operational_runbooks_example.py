from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1] / "examples/operational-runbooks"


class OperationalRunbooksExampleTest(unittest.TestCase):
    def test_example_schema_accepts_a_grounded_match_and_rejects_forced_no_match(self) -> None:
        schema = json.loads((
            ROOT / "catalog/commands/acme-cmd-detect-runbook-use-case/references/output.schema.json"
        ).read_text(encoding="utf-8"))
        match = {
            "schema_version": 1,
            "status": "matched",
            "observed_facts": ["Job J-123 has remained pending since 10:15"],
            "matches": [{
                "scenario": "delayed-background-job",
                "affinity": "medium",
                "matched_symptoms": ["operation remains pending"],
                "distinguishing_checks": ["confirm whether an enqueue event exists"],
                "runbook": "runbooks/example-delayed-job.md",
                "section": "First safe check",
                "first_step": "Look up the exact job identifier through the read-only observability interface.",
                "expected_result": "One enqueue event is found, or the investigation returns to the producer.",
            }],
            "excluded": [],
        }
        jsonschema.validate(match, schema)
        invalid = {**match, "status": "no-match"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_example_contains_no_enabu_specific_content(self) -> None:
        for path in ROOT.rglob("*"):
            if path.is_file():
                self.assertNotIn("enabu", path.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
