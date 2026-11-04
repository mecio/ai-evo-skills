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
SCRIPT = EXAMPLE / "scripts/acme-rebase-git-stack"
ORCHESTRATOR = EXAMPLE / "scripts/acme-rebase-and-republish-github-stack"
REPUBLISH = EXAMPLE / "scripts/acme-republish-rebased-git-stack"
ISSUE = 12724
OUTPUT_SCHEMA = json.loads((EXAMPLE / "catalog/commands/acme-cmd-rebase-git-stack/references/output.schema.json").read_text(encoding="utf-8"))
REPORT_SCHEMA = json.loads((EXAMPLE / "catalog/commands/acme-cmd-report-github-issue-workflow/references/output.schema.json").read_text(encoding="utf-8"))
ORCHESTRATOR_SCHEMA = json.loads((EXAMPLE / "catalog/commands/acme-cmd-rebase-and-republish-github-stack/references/output.schema.json").read_text(encoding="utf-8"))


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


class RebaseGitStackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def oid(self, repo: Path, ref: str) -> str:
        return run("git", "rev-parse", ref, cwd=repo).stdout.strip()

    def remote_oid(self, repo: Path, branch: str) -> str:
        line = run("git", "ls-remote", "origin", f"refs/heads/{branch}", cwd=repo).stdout.strip()
        return line.split()[0] if line else ""

    def write_publication(self, repo: Path, sequence: int, branch: str, parent: str,
                          remote_oid: str, base_oid: str) -> None:
        name = f"issue-{ISSUE}/attempt-01/layers/L{sequence}/04-implement-attempt-01"
        directory = repo / ".ai-evo-work" / name
        directory.mkdir(parents=True)
        (directory / "session.json").write_text(json.dumps({
            "session_name": name,
            "session_slug": name,
            "recipe_name": "acme-recipe-04-implement-github-issue",
            "session_input": {"branch": branch},
            "status": "completed",
            "entries": [{"step_name": "publish_branch", "outcome": "succeeded", "file": "001-publish.json"}],
        }), encoding="utf-8")
        (directory / "001-publish.json").write_text(json.dumps({"output": json.dumps({
            "branch": branch, "parent_branch": parent, "remote": "origin", "remote_oid": remote_oid,
            "base_oid": base_oid, "parent_oid": base_oid,
        })}), encoding="utf-8")

    def repository(self, layers: int = 2, advance_trunk: bool = True,
                   conflict_on_second: bool = False, separate_worktrees: bool = False) -> dict[str, object]:
        remote = self.base / "origin.git"
        repo = self.base / "repo"
        run("git", "init", "--bare", "-q", str(remote), cwd=self.base)
        run("git", "init", "-q", "-b", "main", str(repo), cwd=self.base)
        run("git", "config", "user.name", "Test", cwd=repo)
        run("git", "config", "user.email", "test@example.invalid", cwd=repo)
        run("git", "config", "core.commentChar", ";", cwd=repo)
        (repo / ".ai-evo").mkdir()
        (repo / ".git/info/exclude").write_text(".ai-evo/\n.ai-evo-work/\n", encoding="utf-8")
        (repo / "shared.txt").write_text("base\n", encoding="utf-8")
        run("git", "add", "shared.txt", cwd=repo)
        run("git", "commit", "-qm", "initial", cwd=repo)
        initial = self.oid(repo, "HEAD")
        run("git", "remote", "add", "origin", str(remote), cwd=repo)
        run("git", "push", "-qu", "origin", "main", cwd=repo)

        branches: list[str] = []
        old_oids: dict[str, str] = {}
        parent = "main"
        parent_oid = initial
        for index in range(layers):
            branch = f"feature/issue-{ISSUE}/0{index}-layer"
            run("git", "switch", "-qc", branch, parent, cwd=repo)
            if conflict_on_second and index == 1:
                (repo / "shared.txt").write_text("layer one\n", encoding="utf-8")
                run("git", "add", "shared.txt", cwd=repo)
            else:
                path = repo / f"layer-{index}.txt"
                path.write_text(f"layer {index}\n", encoding="utf-8")
                run("git", "add", path.name, cwd=repo)
            run("git", "commit", "-qm", f"#{ISSUE} layer {index}", cwd=repo)
            layer_oid = self.oid(repo, "HEAD")
            run("git", "push", "-qu", "origin", branch, cwd=repo)
            self.write_publication(repo, index, branch, parent, layer_oid, parent_oid)
            branches.append(branch)
            old_oids[branch] = layer_oid
            parent, parent_oid = branch, layer_oid

        common = Path(run("git", "rev-parse", "--git-common-dir", cwd=repo).stdout.strip())
        if not common.is_absolute():
            common = repo / common
        (common / "gh-stack").write_text(json.dumps({
            "stacks": [{"trunk": {"branch": "main"},
                        "branches": [{"branch": branch} for branch in branches]}],
        }), encoding="utf-8")

        worktrees: dict[str, Path] = {}
        if separate_worktrees:
            trunk_path = self.base / "trunk-worktree"
            first_path = self.base / "layer-zero-worktree"
            run("git", "worktree", "add", "-q", str(trunk_path), "main", cwd=repo)
            run("git", "worktree", "add", "-q", str(first_path), branches[0], cwd=repo)
            worktrees.update({"main": trunk_path, branches[0]: first_path, branches[-1]: repo})

        trunk_oid = initial
        if advance_trunk:
            publisher = self.base / "publisher"
            run("git", "clone", "-q", "-b", "main", str(remote), str(publisher), cwd=self.base)
            run("git", "config", "user.name", "Publisher", cwd=publisher)
            run("git", "config", "user.email", "publisher@example.invalid", cwd=publisher)
            if conflict_on_second:
                (publisher / "shared.txt").write_text("trunk version\n", encoding="utf-8")
                run("git", "add", "shared.txt", cwd=publisher)
            else:
                (publisher / "trunk.txt").write_text("advanced\n", encoding="utf-8")
                run("git", "add", "trunk.txt", cwd=publisher)
            run("git", "commit", "-qm", "advance trunk", cwd=publisher)
            run("git", "push", "-q", "origin", "main", cwd=publisher)
            trunk_oid = self.oid(publisher, "main")

        return {"repo": repo, "branches": branches, "old_oids": old_oids,
                "initial": initial, "trunk_oid": trunk_oid, "worktrees": worktrees}

    def invoke(self, repo: Path, authorized: bool) -> dict[str, object]:
        result = run(str(SCRIPT), "rebase", json.dumps({
            "issue": str(ISSUE), "publication_authorized": authorized,
        }), cwd=repo, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        jsonschema.validate(output, OUTPUT_SCHEMA)
        return output

    def invoke_orchestrator(self, repo: Path, authorized: bool) -> dict[str, object]:
        result = run(str(ORCHESTRATOR), "run", json.dumps({
            "issue": str(ISSUE), "publication_authorized": authorized,
        }), cwd=repo, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        jsonschema.validate(output, ORCHESTRATOR_SCHEMA)
        return output

    def test_output_contract_covers_workflow_and_rebase_results(self) -> None:
        self.assertIn("oneOf", OUTPUT_SCHEMA)
        self.assertEqual(OUTPUT_SCHEMA, ORCHESTRATOR_SCHEMA)

    def test_recipe_orchestrator_simulates_without_recording_republication(self) -> None:
        state = self.repository(layers=1)
        repo = state["repo"]
        assert isinstance(repo, Path)
        branch = state["branches"][0]

        result = self.invoke_orchestrator(repo, False)

        self.assertEqual("stack-rebase-simulated", result["status"], result)
        self.assertEqual(state["old_oids"][branch], self.oid(repo, branch))
        self.assertEqual(state["old_oids"][branch], self.remote_oid(repo, branch))
        self.assertEqual([], list((repo / ".ai-evo-work").glob("**/04r-republish-attempt-*")))

    def test_recipe_orchestrator_records_04r_after_authorized_rebase(self) -> None:
        state = self.repository(layers=2, separate_worktrees=True)
        repo = state["repo"]
        assert isinstance(repo, Path)

        result = self.invoke_orchestrator(repo, True)

        self.assertNotEqual("stack-rebase-required", result["status"], result)
        self.assertNotEqual("stack-republish-required", result["status"], result)
        recorded = list((repo / ".ai-evo-work").glob("**/04r-republish-attempt-*/session.json"))
        self.assertEqual(2, len(recorded))
        self.assertEqual(
            {"acme-recipe-rebase-and-republish-github-stack"},
            {json.loads(path.read_text(encoding="utf-8"))["recipe_name"] for path in recorded},
        )
        for branch in state["branches"]:
            self.assertEqual(self.remote_oid(repo, branch), self.oid(repo, branch))

    def test_without_publications_returns_the_report_without_fetching(self) -> None:
        repo = self.base / "empty-workflow"
        run("git", "init", "-q", "-b", "main", str(repo), cwd=self.base)
        run("git", "config", "user.name", "Test", cwd=repo)
        run("git", "config", "user.email", "test@example.invalid", cwd=repo)
        (repo / ".ai-evo").mkdir()
        (repo / "README").write_text("test\n", encoding="utf-8")
        run("git", "add", "README", cwd=repo)
        run("git", "commit", "-qm", "initial", cwd=repo)
        expected = json.loads(run(
            str(EXAMPLE / "scripts/acme-report-github-issue-workflow"), "report", "--issue", str(ISSUE), cwd=repo,
        ).stdout)

        self.assertEqual(expected, self.invoke(repo, False))

    def test_intermediate_parent_case_is_rejected_without_git_mutations(self) -> None:
        loader = SourceFileLoader("rebase_git_stack_for_test", str(SCRIPT))
        spec = spec_from_loader(loader.name, loader)
        assert spec is not None
        module = module_from_spec(spec)
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            loader.exec_module(module)
        finally:
            sys.path.pop(0)
        layer = {"branch": "child", "parent_branch": "parent", "remote": "origin", "remote_oid": "a" * 40}
        report = {
            "status": "stack-rebase-required",
            "resolved_inputs": {"issue": str(ISSUE), "branch": "child", "parent_branch": "parent"},
        }
        output: list[dict[str, object]] = []
        with (mock.patch.object(sys, "argv", [str(SCRIPT), "rebase", json.dumps({
                  "issue": ISSUE, "publication_authorized": False,
              })]),
              mock.patch.object(module, "published_layers", return_value=[layer]),
              mock.patch.object(module, "order_layers", return_value=("main", [layer])),
              mock.patch.object(module, "fetch_stack", return_value=""),
              mock.patch.object(module, "report", return_value=report),
              mock.patch.object(module, "write_json", side_effect=output.append)):
            self.assertEqual(0, module.main())
        self.assertEqual("stack-rebase-blocked", output[0]["status"])
        self.assertEqual("unsupported-rebase-case", output[0]["code"])
        self.assertEqual([], output[0]["details"]["modified_refs"])

    def test_returns_report_unchanged_when_trunk_has_not_advanced(self) -> None:
        state = self.repository(layers=1, advance_trunk=False)
        repo = state["repo"]
        assert isinstance(repo, Path)

        result = self.invoke(repo, False)

        self.assertNotEqual("stack-rebase-simulated", result["status"])
        self.assertNotEqual("stack-rebase-blocked", result["status"])
        branch = state["branches"][0]
        self.assertEqual(state["old_oids"][branch], self.oid(repo, branch))

    def test_simulates_two_layers_without_moving_branches_or_worktrees(self) -> None:
        state = self.repository(separate_worktrees=True)
        repo = state["repo"]
        assert isinstance(repo, Path)
        before = {branch: self.oid(repo, branch) for branch in ["main", *state["branches"]]}

        first = self.invoke(repo, False)
        second = self.invoke(repo, False)

        self.assertEqual("stack-rebase-simulated", first["status"])
        self.assertEqual("stack-rebase-simulated", second["status"])
        self.assertEqual([item["patch_ids"] for item in first["layers"]],
                         [item["patch_ids"] for item in second["layers"]])
        self.assertEqual(before, {branch: self.oid(repo, branch) for branch in before})
        for branch, path in state["worktrees"].items():
            self.assertEqual(before[branch], self.oid(path, "HEAD"))
            self.assertEqual("", run("git", "status", "--porcelain", cwd=path).stdout)
        for branch in state["branches"]:
            self.assertEqual(state["old_oids"][branch], self.remote_oid(repo, branch))

    def test_authorized_rebase_pushes_then_aligns_trunk_layers_and_worktrees(self) -> None:
        state = self.repository(separate_worktrees=True)
        repo = state["repo"]
        assert isinstance(repo, Path)

        result = self.invoke(repo, True)

        self.assertEqual("stack-republish-required", result["status"], result)
        self.assertEqual(state["trunk_oid"], self.oid(repo, "main"))
        for branch in state["branches"]:
            self.assertEqual(self.remote_oid(repo, branch), self.oid(repo, branch))
            self.assertNotEqual(state["old_oids"][branch], self.oid(repo, branch))
        for branch, path in state["worktrees"].items():
            self.assertEqual(self.oid(repo, branch), self.oid(path, "HEAD"))
            self.assertEqual("", run("git", "status", "--porcelain", cwd=path).stdout)
            self.assertTrue((path / "trunk.txt").is_file())
        self.assertTrue((state["worktrees"][state["branches"][0]] / "layer-0.txt").is_file())
        recorded = run(str(REPUBLISH), "republish", json.dumps({
            "issue": ISSUE, "publication_authorized": True,
        }), cwd=repo, check=False)
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        self.assertEqual("republished", json.loads(recorded.stdout)["status"])
        repeated = self.invoke(repo, True)
        self.assertNotEqual("stack-rebase-required", repeated["status"])

    def test_conflict_on_second_layer_leaves_every_ref_unchanged(self) -> None:
        state = self.repository(conflict_on_second=True)
        repo = state["repo"]
        assert isinstance(repo, Path)
        before = {branch: self.oid(repo, branch) for branch in ["main", *state["branches"]]}

        result = self.invoke(repo, True)

        self.assertEqual("stack-rebase-conflict", result["status"], result)
        self.assertEqual(state["branches"][1], result["layer"])
        self.assertEqual(["shared.txt"], result["files"])
        self.assertEqual(before, {branch: self.oid(repo, branch) for branch in before})
        for branch in state["branches"]:
            self.assertEqual(state["old_oids"][branch], self.remote_oid(repo, branch))

    def test_pre_rebase_hook_failure_blocks_beside_the_same_hook_free_stack(self) -> None:
        state = self.repository(layers=1)
        repo = state["repo"]
        assert isinstance(repo, Path)
        hook = repo / ".git/hooks/pre-rebase"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

        blocked = self.invoke(repo, False)
        self.assertEqual("stack-rebase-blocked", blocked["status"])
        self.assertEqual("rebase-failed", blocked["code"], blocked)

        hook.unlink()
        healthy = self.invoke(repo, False)
        self.assertEqual("stack-rebase-simulated", healthy["status"], healthy)

    def test_dirty_layer_worktree_blocks_beside_clean_case(self) -> None:
        state = self.repository(separate_worktrees=True)
        repo = state["repo"]
        assert isinstance(repo, Path)
        path = state["worktrees"][state["branches"][0]]
        (path / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        blocked = self.invoke(repo, False)
        self.assertEqual("stack-rebase-blocked", blocked["status"])
        self.assertEqual("dirty-worktree", blocked["code"])

        (path / "dirty.txt").unlink()
        healthy = self.invoke(repo, False)
        self.assertEqual("stack-rebase-simulated", healthy["status"], healthy)

    def test_divergent_local_trunk_blocks_while_behind_trunk_is_simulatable(self) -> None:
        state = self.repository(layers=1)
        repo = state["repo"]
        assert isinstance(repo, Path)
        healthy = self.invoke(repo, False)
        self.assertEqual("stack-rebase-simulated", healthy["status"], healthy)

        tree = self.oid(repo, "main^{tree}")
        local_commit = run("git", "commit-tree", tree, "-p", self.oid(repo, "main"), "-m", "local trunk",
                           cwd=repo, check=True,).stdout.strip()
        run("git", "update-ref", "refs/heads/main", local_commit, self.oid(repo, "main"), cwd=repo)
        blocked = self.invoke(repo, False)
        self.assertEqual("stack-rebase-blocked", blocked["status"])
        self.assertEqual("trunk-not-fast-forward", blocked["code"], blocked)
        self.assertTrue(blocked["details"]["local_commits"])

    def test_unexpected_comment_character_is_only_a_warning(self) -> None:
        state = self.repository(layers=1)
        repo = state["repo"]
        assert isinstance(repo, Path)
        run("git", "config", "core.commentChar", "#", cwd=repo)

        result = self.invoke(repo, False)

        self.assertEqual("stack-rebase-simulated", result["status"], result)
        self.assertTrue(any("core.commentChar" in warning for warning in result["warnings"]))

    def test_missing_upstream_blocks_beside_the_same_aligned_branch(self) -> None:
        state = self.repository(layers=1)
        repo = state["repo"]
        assert isinstance(repo, Path)
        branch = state["branches"][0]
        run("git", "branch", "--unset-upstream", branch, cwd=repo)

        blocked = self.invoke(repo, False)
        self.assertEqual("local-remote-divergence", blocked["code"], blocked)

        run("git", "branch", f"--set-upstream-to=origin/{branch}", branch, cwd=repo)
        healthy = self.invoke(repo, False)
        self.assertEqual("stack-rebase-simulated", healthy["status"], healthy)

    def test_atomic_push_unsupported_keeps_local_and_remote_layer_refs(self) -> None:
        state = self.repository()
        repo = state["repo"]
        assert isinstance(repo, Path)
        remote_path = Path(run("git", "remote", "get-url", "origin", cwd=repo).stdout.strip())
        run("git", "config", "receive.advertiseAtomic", "false", cwd=remote_path)

        result = self.invoke(repo, True)

        self.assertEqual("stack-rebase-blocked", result["status"])
        self.assertEqual("atomic-push-unsupported", result["code"], result)
        for branch in state["branches"]:
            self.assertEqual(state["old_oids"][branch], self.oid(repo, branch))
            self.assertEqual(state["old_oids"][branch], self.remote_oid(repo, branch))


if __name__ == "__main__":
    unittest.main()
