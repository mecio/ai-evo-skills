from __future__ import annotations

import hashlib
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_cli as fixtures
import jsonschema
import yaml


EXAMPLE = fixtures.ENGINE / "examples/acme"
CATALOG = EXAMPLE / "catalog"
SCRIPTS = EXAMPLE / "scripts"


def load_extensionless(name: str, path: Path):
    loader = SourceFileLoader(name, str(path))
    spec = spec_from_loader(loader.name, loader)
    assert spec is not None
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


class AcmeWorkflowCatalogTest(unittest.TestCase):
    def test_catalog_validates_and_syncs_with_scripts_and_capabilities(self) -> None:
        case = fixtures.CliIntegrationTest()
        temporary, root = case.repository()
        with temporary:
            initialized = case.run_cli(
                root, "init", "--namespace", "acme", "--adapter", "codex", "--adapter", "claude"
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            project = root / ".ai-evo-prj"
            shutil.copytree(CATALOG, project / "skills/catalog", dirs_exist_ok=True)
            shutil.copytree(SCRIPTS, project / "scripts", dirs_exist_ok=True)
            shutil.copytree(EXAMPLE / "config", project / "skills/config", dirs_exist_ok=True)
            for arguments in (("validate",), ("sync", "--dry-run"), ("sync",)):
                result = case.run_cli(root, *arguments)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_recipe_instructions_always_select_the_current_adapter(self) -> None:
        for path in (CATALOG / "recipes").glob("*/SKILL.md"):
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if "recipe plan" in line]
            for line in lines:
                with self.subTest(recipe=path.parent.name):
                    self.assertIn("--adapter <adapter-corrente>", line)

    def test_declared_project_capabilities_are_registered(self) -> None:
        capabilities = yaml.safe_load((EXAMPLE / "config/execution-capabilities.yaml").read_text(encoding="utf-8"))
        registered = set(capabilities["capabilities"])
        for path in (CATALOG / "commands").glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            match = re.search(r"^  capabilities: \[([^]]*)\]$", text, flags=re.MULTILINE)
            if not match:
                continue
            for capability in (item.strip() for item in match.group(1).split(",")):
                if capability.startswith("acme."):
                    self.assertIn(capability, registered, path.parent.name)

    def test_resume_accepts_runtime_scalar_forms(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            resume = load_extensionless("acme_resume_workflow", SCRIPTS / "acme-resume-github-issue-workflow")
        finally:
            sys.path.pop(0)
        self.assertEqual((12603, False), resume.request('{"issue":"12603","publication_authorized":"false"}'))
        self.assertEqual((12603, True), resume.request('{"issue":12603,"publication_authorized":"true"}'))

    def test_ready_transition_is_recorded_without_rewriting_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ai-evo").mkdir()
            output = '{"status":"ready"}\n'
            transition = {
                "status": "ready",
                "step": {
                    "uses": "acme-cmd-save-worklog-output",
                    "with": {
                        "session_name": "issue-12603/attempt-01/02-analyze-attempt-01",
                        "recipe_name": "acme-recipe-02-analyze-github-issue-code",
                        "session_input": '{"issue":"12603"}',
                        "step_name": "analyze_issue",
                        "source_name": "acme-cmd-analyze-github-issue-code",
                        "outcome": "succeeded",
                        "output": output,
                        "expected_output_sha256": hashlib.sha256(output.encode()).hexdigest(),
                        "error": "null",
                        "complete": "true",
                    },
                },
            }
            result = subprocess.run(
                [str(SCRIPTS / "acme-operation-output-worklog"), "record-from-transition"],
                cwd=root,
                input=json.dumps(transition),
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(output, result.stdout)
            session = root / ".ai-evo-work/issue-12603/attempt-01/02-analyze-attempt-01"
            record = next(session.glob("[0-9]*.json"))
            self.assertEqual(output, json.loads(record.read_text(encoding="utf-8"))["output"])
            self.assertEqual("completed", json.loads((session / "session.json").read_text())["status"])

    def test_push_branch_helper_publishes_the_exact_implementation_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            remote = base / "remote.git"
            root = base / "application"
            subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
            root.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
            (root / "file.txt").write_text("main\n", encoding="utf-8")
            (root / ".gitignore").write_text(".ai-evo-prj/\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt", ".gitignore"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=root, check=True)
            project = root / ".ai-evo-prj"
            shutil.copytree(SCRIPTS, project / "scripts")
            shutil.copytree(EXAMPLE / "config", project / "skills/config")
            subprocess.run(["git", "switch", "-qc", "feature/layer"], cwd=root, check=True)
            (root / "file.txt").write_text("layer\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-qam", "#12603 layer"], cwd=root, check=True)
            oid = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            report = {
                "branch": "feature/layer",
                "parent_branch": "main",
                "base_branch": "main",
                "sequence": 0,
                "commits": [{"sha": oid, "subject": "#12603 layer"}],
            }
            result = subprocess.run(
                [str(project / "scripts/acme-git-local"), "push-branch", json.dumps({"implementation_report": report})],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(result.stdout)
            schema_path = CATALOG / "commands/acme-cmd-push-git-stacked-branch/references/output.schema.json"
            jsonschema.Draft202012Validator(json.loads(schema_path.read_text())).validate(receipt)
            self.assertEqual(oid, receipt["local_oid"])
            self.assertEqual(oid, receipt["remote_oid"])
            remote_oid = subprocess.check_output(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/feature/layer"], text=True
            ).strip()
            self.assertEqual(oid, remote_oid)

    def test_commit_helper_can_commit_one_planned_subset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
            for name in ("first.txt", "second.txt"):
                (root / name).write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
            for name in ("first.txt", "second.txt"):
                (root / name).write_text("after\n", encoding="utf-8")
            inspected = subprocess.run(
                [str(SCRIPTS / "acme-git-local"), "inspect"], cwd=root, capture_output=True, text=True
            )
            self.assertEqual(0, inspected.returncode, inspected.stderr)
            plan = json.loads(inspected.stdout)
            plan.update({
                "status": "ready",
                "issue": 12603,
                "summary": "Commit first file",
                "risks": [],
                "missing_verifications": [],
                "message": "#12603 Commit first file\n\nKeep the second change for another commit.\n",
                "paths": ["first.txt"],
                "files": [item for item in plan["files"] if item["path"] == "first.txt"],
            })
            result = subprocess.run(
                [str(SCRIPTS / "acme-git-local"), "commit", json.dumps(plan)],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            changed = subprocess.check_output(["git", "status", "--short"], cwd=root, text=True)
            self.assertEqual(" M second.txt\n", changed)

    def test_local_worktree_configuration_overrides_shared_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "vms/application"
            root.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", root], check=True)
            project = root / ".ai-evo-prj"
            shutil.copytree(SCRIPTS, project / "scripts")
            shutil.copytree(EXAMPLE / "config", project / "skills/config")
            (project / "acme-worktrees.local.yaml").write_text(
                'legacy_root: "./vms/application"\n', encoding="utf-8"
            )
            result = subprocess.run(
                [str(project / "scripts/acme-worktree-context"), "--field", "context"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("legacy\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
