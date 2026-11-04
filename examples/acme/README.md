# Acme workflow catalog

This is a copyable GitHub delivery workflow modeled on a production catalog. `acme` is a placeholder namespace;
replace it consistently when adopting the catalog. Each recipe defaults to the invoking AI through
`command_executor=current`; pass an installed adapter ID to select AI and GitHub steps. Local project scripts and
their worklog checkpoints run through Claude, whose adapter grants their fixed command capabilities.

## Install the catalog

Run from the application repository root, with the engine checkout linked as `.ai-evo`.

```bash
./.ai-evo/bin/ai-evo-skills init --namespace acme --adapter codex --adapter claude
cp -R .ai-evo/examples/acme/catalog/. .ai-evo-prj/skills/catalog/
cp -R .ai-evo/examples/acme/scripts/. .ai-evo-prj/scripts/
cp -R .ai-evo/examples/acme/config/. .ai-evo-prj/skills/config/
cp -R .ai-evo/examples/acme/supervisors .ai-evo-prj/skills/
cp .ai-evo/examples/acme/acme-recipes.md .ai-evo-prj/skills/acme-recipes.md
cp .ai-evo/examples/acme/post-workflow-publishers.md .ai-evo-prj/skills/post-workflow-publishers.md
./.ai-evo/bin/ai-evo-skills validate
./.ai-evo/bin/ai-evo-skills sync --dry-run
./.ai-evo/bin/ai-evo-skills sync
```

Before running a recipe, replace every placeholder in `acme-worktrees.yaml` and `acme-git-branches.yaml` with the
project's worktree roots, runtime and lint commands, branch strategy and stack tool. The helpers are copied as a starting
implementation; validate their behavior against the repository before allowing commits, pushes or pull requests.
The catalog requires the Claude adapter for the fixed, capability-scoped local scripts; Codex can run the AI and
GitHub steps through the default executor or `command_executor=codex`.
For machine-specific worktree roots, copy `acme-worktrees.local.tpl.yaml` to
`.ai-evo-prj/acme-worktrees.local.yaml`, add the destination to the application `.gitignore`, and set only the
values that differ locally. `acme-worktree-context` merges this ignored file over the shared configuration.

## Workflow

The catalog contains 42 direct commands and 14 recipes. Recipe steps call specific operations and record immutable
worklog checkpoints; there is no generic workflow-phase command.

| Phase | Recipe | Outcome |
|---|---|---|
| 00 | `acme-recipe-00-design-github-issue` | Designed and created issue. |
| 01 | `acme-recipe-01-refine-github-issue` | Refined requirements. |
| 02 | `acme-recipe-02-analyze-github-issue-code` | Evidence-backed code analysis. |
| 03 | `acme-recipe-03-breakdown-github-issue` | Work-item or stacked-work plan. |
| 03 | `acme-recipe-03-breakdown-github-issue-local` | Local-only breakdown without GitHub writes. |
| 04 | `acme-recipe-04-adopt-github-issue-layer` | Approved adoption of an existing layer. |
| 04 | `acme-recipe-04-implement-github-issue` | Implemented work item and local evidence. |
| 04 | `acme-recipe-04-implement-github-issue-correction` | Correction of an unpublished implementation. |
| 05 | `acme-recipe-05-review-github-issue` | Review and branch verification. |
| 06 | `acme-recipe-06-verify-github-epic-stack` | Epic-level completion evidence. |
| 07 | `acme-recipe-07-push-github-stack` | Authorized publication report. |
| 08 | `acme-recipe-08-submit-github-stack` | Authorized pull-request submission. |
| bridge | `acme-recipe-rebase-and-republish-github-stack` | Atomic stack rebase and authorized republication. |
| bridge | `acme-recipe-resume-github-issue-workflow` | Recover a published branch and resolve the next workflow action. |

Start with phase 00. Each later recipe receives its issue, worklog session and immutable input from the previous
checkpoint through `acme-cmd-report-github-issue-workflow`. Review the resolved input and invoke only the next
appropriate phase. Phases 07 and 08 require explicit publication authorization.
When the resolver reports `branch-recovery-required`, run the bridge recipe. If the trunk advanced after the
recorded publication, it returns `stack-rebase-required` and leaves rebase and push to the project's documented
recovery recipe. First run it in simulation mode; only an explicitly authorized execution may atomically update
the remote stack. The recipe verifies patch equivalence, records the new remote OIDs and allows the workflow to
resume.

The example also includes optional operational helpers: isolated issue workspaces, archival of closed issue
worklogs and policy-driven supervision up to a local result or draft PRs. They remain separate from the core
recipes so projects can adopt them independently. See [post-workflow publishers](post-workflow-publishers.md) for
the contract of optional reports, indexes or deployment triggers that run after a verified outcome.

`acme-recipes.md` describes the worklog layout and recovery rules. The [authoring guide](../../docs/authoring.md)
describes command and recipe contracts, while [command scripts](../../docs/command-scripts.md) covers helper
ownership and verification.

## Why use recipes and commands

Use a direct prompt for exploration or a one-off fix. Recipes become useful when work changes a repository or
GitHub: they make the approved scope, immutable inputs, checkpoints, tests, publication and recovery evidence
explicit. Commands keep each operation small and verifiable, so another agent can resume from the recorded state
without reconstructing it from conversation history.
