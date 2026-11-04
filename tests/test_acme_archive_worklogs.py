from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/acme"
SCRIPT = EXAMPLE / "scripts/acme-archive-closed-github-issue-worklogs"
SCHEMA = EXAMPLE / "catalog/commands/acme-cmd-archive-closed-github-issue-worklogs/references/output.schema.json"


class ArchiveClosedGithubIssueWorklogsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        (self.workspace / ".ai-evo").mkdir()
        self.worklogs = self.workspace / ".ai-evo-work"
        self.worklogs.mkdir()
        for name in ("issue-12", "issue-13", "issue-pending"):
            (self.worklogs / name).mkdir()
            (self.worklogs / name / "evidence.txt").write_text(name, encoding="utf-8")
        self.bin = Path(self.temporary.name) / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(
            "#!/usr/bin/env python3\n"
            "import fcntl, json, os, sys\n"
            "issue = int(sys.argv[3])\n"
            "if os.environ.get('ASSERT_UNLOCKED_ROOT'):\n"
            "    descriptor = os.open(os.environ['ASSERT_UNLOCKED_ROOT'], os.O_RDONLY | os.O_DIRECTORY)\n"
            "    try:\n"
            "        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
            "    except BlockingIOError:\n"
            "        print('worklog root is locked during GitHub read', file=sys.stderr)\n"
            "        raise SystemExit(2)\n"
            "    finally:\n"
            "        os.close(descriptor)\n"
            "if os.environ.get('FAIL_ISSUE') == str(issue):\n"
            "    print('unavailable', file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "if os.environ.get('MUTATE_ON_ISSUE') == str(issue):\n"
            "    with open(os.environ['MUTATE_PATH'], 'w', encoding='utf-8') as stream:\n"
            "        stream.write('changed')\n"
            "states = json.loads(os.environ.get('ISSUE_STATES', '{}'))\n"
            "state = states.get(str(issue), 'CLOSED' if issue == 12 else 'OPEN')\n"
            "print(json.dumps({'number': issue, 'state': state, 'url': f'https://example.test/issues/{issue}'}))\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, dry_run: bool, **environment: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", **environment}
        return subprocess.run(
            [str(SCRIPT), "archive", json.dumps({"dry_run": dry_run})],
            cwd=self.workspace,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_dry_run_reports_closed_issues_without_moving_them(self) -> None:
        result = self.invoke(True)
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(output)
        self.assertEqual((2, 1, 1, 1, 0),
                         (output["checked"], output["open"], output["closed"], output["archivable"], output["archived"]))
        self.assertEqual("dry-run", output["status"])
        self.assertTrue((self.worklogs / "issue-12/evidence.txt").is_file())
        self.assertFalse((self.worklogs / "archive").exists())

    def test_apply_moves_only_closed_top_level_issue_roots(self) -> None:
        (self.worklogs / "archive/issue-99").mkdir(parents=True)
        (self.worklogs / "archive/issue-99/evidence.txt").write_text("archived", encoding="utf-8")
        result = self.invoke(False)
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("archived", output["status"])
        self.assertEqual(1, output["archived"])
        self.assertFalse((self.worklogs / "issue-12").exists())
        self.assertTrue((self.worklogs / "archive/issue-12/evidence.txt").is_file())
        self.assertTrue((self.worklogs / "archive/issue-99/evidence.txt").is_file())
        self.assertTrue((self.worklogs / "issue-13/evidence.txt").is_file())
        self.assertTrue((self.worklogs / "issue-pending/evidence.txt").is_file())

    def test_closed_epic_with_open_subissue_remains_active(self) -> None:
        child = self.worklogs / "issue-12/attempt-01/subissues/issue-14"
        child.mkdir(parents=True)
        result = self.invoke(False, ISSUE_STATES=json.dumps({"14": "OPEN"}))
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        epic = next(entry for entry in output["entries"] if entry["issue"] == 12)
        self.assertEqual("keep", epic["action"])
        self.assertEqual("open-subissues", epic["reason"])
        self.assertEqual([14], epic["open_subissues"])
        self.assertEqual(1, output["subissues_checked"])
        self.assertEqual(0, output["archivable"])
        self.assertTrue((self.worklogs / "issue-12").is_dir())

    def test_closed_epic_is_archived_when_all_distinct_subissues_are_closed(self) -> None:
        for attempt in ("attempt-01", "attempt-02"):
            (self.worklogs / f"issue-12/{attempt}/subissues/issue-14").mkdir(parents=True)
        (self.worklogs / "issue-12/attempt-02/subissues/issue-15").mkdir()
        result = self.invoke(False, ISSUE_STATES=json.dumps({"14": "CLOSED", "15": "CLOSED"}))
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        epic = next(entry for entry in output["entries"] if entry["issue"] == 12)
        self.assertEqual("archive", epic["action"])
        self.assertEqual([14, 15], [child["issue"] for child in epic["subissues"]])
        self.assertEqual(2, output["subissues_checked"])
        self.assertTrue((self.worklogs / "archive/issue-12").is_dir())

    def test_remote_failure_prevents_all_moves(self) -> None:
        result = self.invoke(False, FAIL_ISSUE="13")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("cannot read GitHub issue 13", result.stderr)
        self.assertTrue((self.worklogs / "issue-12").is_dir())
        self.assertFalse((self.worklogs / "archive").exists())

    def test_existing_archive_destination_prevents_all_moves(self) -> None:
        (self.worklogs / "archive/issue-12").mkdir(parents=True)
        result = self.invoke(False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("archive destination already exists", result.stderr)
        self.assertTrue((self.worklogs / "issue-12").is_dir())

    def test_github_reads_do_not_hold_the_worklog_lock(self) -> None:
        result = self.invoke(True, ASSERT_UNLOCKED_ROOT=str(self.worklogs))
        self.assertEqual(0, result.returncode, result.stderr)

    def test_local_change_during_remote_verification_prevents_all_moves(self) -> None:
        changed = self.worklogs / "issue-12/changed.txt"
        result = self.invoke(False, MUTATE_ON_ISSUE="13", MUTATE_PATH=str(changed))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("changed during GitHub verification", result.stderr)
        self.assertTrue((self.worklogs / "issue-12").is_dir())
        self.assertFalse((self.worklogs / "archive").exists())

    def test_active_session_blocks_closed_issue_archival_without_changing_state(self) -> None:
        session = self.worklogs / "issue-12/attempt-01/02-analyze-attempt-01"
        session.mkdir(parents=True)
        (session / "session.json").write_text(json.dumps({"status": "active"}), encoding="utf-8")
        (session / "context.md").write_text(
            "# Worklog\n\n- Status: `active`\n- Updated: `2026-10-19T10:00:00Z`\n",
            encoding="utf-8",
        )
        result = self.invoke(False)
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        issue = next(entry for entry in output["entries"] if entry["issue"] == 12)
        self.assertEqual("keep", issue["action"])
        self.assertEqual("active-worklog", issue["reason"])
        self.assertEqual(["attempt-01/02-analyze-attempt-01"], issue["local_blockers"])
        self.assertEqual("active", json.loads((session / "session.json").read_text(encoding="utf-8"))["status"])
        self.assertIn("- Status: `active`", (session / "context.md").read_text(encoding="utf-8"))
        self.assertFalse((self.worklogs / "archive/issue-12").exists())

    def test_dry_run_does_not_complete_active_local_state(self) -> None:
        session = self.worklogs / "issue-12/attempt-01/02-analyze-attempt-01"
        session.mkdir(parents=True)
        session_path = session / "session.json"
        session_path.write_text(json.dumps({"status": "active"}), encoding="utf-8")
        result = self.invoke(True)
        self.assertEqual(0, result.returncode, result.stderr)
        issue = next(entry for entry in json.loads(result.stdout)["entries"] if entry["issue"] == 12)
        self.assertEqual("keep", issue["action"])
        self.assertEqual("active-worklog", issue["reason"])
        self.assertEqual("active", json.loads(session_path.read_text(encoding="utf-8"))["status"])
        self.assertFalse((self.worklogs / "archive").exists())

    def test_active_supervisor_assignment_blocks_archival_in_real_layout(self) -> None:
        supervisor = self.worklogs / "issue-12/supervisor"
        assignment = supervisor / "runs/run-001/assignment.json"
        run = supervisor / "runs/run-001/run.json"
        run.parent.mkdir(parents=True)
        (supervisor / "state.json").write_text(json.dumps({
            "status": "active", "current_assignment": "run-001",
        }), encoding="utf-8")
        assignment.write_text(json.dumps({"status": "active"}), encoding="utf-8")
        run.write_text(json.dumps({"status": "active"}), encoding="utf-8")
        result = self.invoke(False)
        self.assertEqual(0, result.returncode, result.stderr)
        issue = next(entry for entry in json.loads(result.stdout)["entries"] if entry["issue"] == 12)
        self.assertEqual("keep", issue["action"])
        self.assertEqual(["supervisor"], issue["local_blockers"])
        for path in (supervisor / "state.json", assignment, run):
            self.assertEqual("active", json.loads(path.read_text(encoding="utf-8"))["status"])
        self.assertFalse((self.worklogs / "archive/issue-12").exists())

    def test_active_session_content_is_not_rewritten_during_archival_check(self) -> None:
        session = self.worklogs / "issue-12/attempt-01/02-analyze-attempt-01"
        session.mkdir(parents=True)
        session_path = session / "session.json"
        original = json.dumps({"status": "active"}).encode("utf-8")
        session_path.write_bytes(original)
        (session / "context.md").write_bytes(b"\xff")
        result = self.invoke(False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, session_path.read_bytes())
        self.assertTrue((self.worklogs / "issue-12").is_dir())
        self.assertFalse((self.worklogs / "archive").exists())


if __name__ == "__main__":
    unittest.main()
