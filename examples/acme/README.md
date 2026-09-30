# Acme workflow catalog

This is a copyable GitHub delivery workflow modeled on a production catalog. `acme` is a placeholder namespace;
replace it consistently when adopting the catalog. Recipes use the invoking AI and their YAML does not select a
specific AI.

## Install the catalog

Run from the application repository root, with the engine checkout linked as `.ai-evo`.

```bash
./.ai-evo/bin/ai-evo-skills init --namespace acme --adapter <your-adapter>
cp -R .ai-evo/examples/acme/catalog/. .ai-evo-prj/skills/catalog/
cp -R .ai-evo/examples/acme/scripts/. .ai-evo-prj/scripts/
cp -R .ai-evo/examples/acme/config/. .ai-evo-prj/skills/config/
cp .ai-evo/examples/acme/acme-recipes.md .ai-evo-prj/skills/acme-recipes.md
./.ai-evo/bin/ai-evo-skills validate
./.ai-evo/bin/ai-evo-skills sync --dry-run
./.ai-evo/bin/ai-evo-skills sync
```

Before running a recipe, replace every placeholder in `acme-worktrees.yaml` and `acme-git-branches.yaml` with the
project's worktree roots, runtime and lint commands, branch strategy and stack tool. The helpers are copied as a starting
implementation; validate their behavior against the repository before allowing commits, pushes or pull requests.

## Workflow

The catalog contains 32 direct commands and 11 recipes. Recipe steps call specific operations and record immutable
worklog checkpoints; there is no generic workflow-phase command.

| Phase | Recipe | Outcome |
|---|---|---|
| 00 | `acme-recipe-00-design-github-issue` | Designed and created issue. |
| 01 | `acme-recipe-01-refine-github-issue` | Refined requirements. |
| 02 | `acme-recipe-02-analyze-github-issue-code` | Evidence-backed code analysis. |
| 03 | `acme-recipe-03-breakdown-github-issue` | Work-item or stacked-work plan. |
| 04 | `acme-recipe-04-adopt-github-issue-layer` | Approved adoption of an existing layer. |
| 04 | `acme-recipe-04-implement-github-issue` | Implemented work item and local evidence. |
| 04 | `acme-recipe-04-implement-github-issue-correction` | Correction of an unpublished implementation. |
| 05 | `acme-recipe-05-review-github-issue` | Review and branch verification. |
| 06 | `acme-recipe-06-verify-github-epic-stack` | Epic-level completion evidence. |
| 07 | `acme-recipe-07-push-github-stack` | Authorized publication report. |
| 08 | `acme-recipe-08-submit-github-stack` | Authorized pull-request submission. |

Start with phase 00. Each later recipe receives its issue, worklog session and immutable input from the previous
checkpoint through `acme-cmd-report-github-issue-workflow`. Review the resolved input and invoke only the next
appropriate phase. Phases 07 and 08 require explicit publication authorization.

`acme-recipes.md` describes the worklog layout and recovery rules. The [authoring guide](../../docs/authoring.md)
describes command and recipe contracts, while [command scripts](../../docs/command-scripts.md) covers helper
ownership and verification.
