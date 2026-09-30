# Acme starter catalog

This is a copyable starter catalog for a new project that tracks work in GitHub. It uses the placeholder
namespace `acme`; replace it consistently if the project has another namespace. Recipes use the AI that
invokes them. No recipe name or YAML field selects a specific AI.

## Start a new project

Run these commands from the root of the application repository. The engine checkout is assumed to be linked
as `.ai-evo`.

```bash
./.ai-evo/bin/ai-evo-skills init --namespace acme --adapter <your-adapter>
cp -R .ai-evo/examples/acme/catalog/commands/. .ai-evo-prj/skills/catalog/commands/
cp -R .ai-evo/examples/acme/catalog/recipes/. .ai-evo-prj/skills/catalog/recipes/
./.ai-evo/bin/ai-evo-skills validate
./.ai-evo/bin/ai-evo-skills sync --dry-run
./.ai-evo/bin/ai-evo-skills sync
```

Replace `<your-adapter>` with an enabled adapter identifier. If the project already has a catalog, inspect
name collisions before copying: the commands intentionally overwrite matching files. Run `validate` after
every catalog edit and run `sync` again to publish the new skills to the configured client.

## What the catalog contains

The workflow has nine direct recipes. Each ends with a saved result that the developer reviews before starting
the next phase.

| Phase | Recipe | Outcome |
|---|---|---|
| 00 | `acme-recipe-00-design-github-issue` | Approved issue design. |
| 01 | `acme-recipe-01-refine-github-issue` | Refined issue requirements. |
| 02 | `acme-recipe-02-analyze-github-issue-code` | Evidence-backed implementation analysis. |
| 03 | `acme-recipe-03-breakdown-github-issue` | Single-item, stacked, or epic work map. |
| 04 | `acme-recipe-04-implement-github-issue` | Implemented work item and local evidence. |
| 05 | `acme-recipe-05-review-github-issue` | Review findings and verification result. |
| 06 | `acme-recipe-06-verify-github-epic-stack` | Epic-level dependency and completion evidence. |
| 07 | `acme-recipe-07-push-github-stack` | Authorized publication report. |
| 08 | `acme-recipe-08-submit-github-stack` | Authorized draft pull-request report. |

Commands remain directly invocable when a developer needs only one operation. The shared
`acme-cmd-github-workflow-phase` supplies the generic phase contract; [github-issue-workflow.md](github-issue-workflow.md)
lists the project-specific command names to split out as the catalog grows.

## First use

Start with phase 00 and describe the problem. After approving its result, pass the saved artifact or its
relevant context to phase 02. Do not skip to implementation before the issue and analysis are approved.

```text
$acme-recipe-00-design-github-issue context="<initial problem and desired outcome>"
$acme-recipe-02-analyze-github-issue-code context="<approved issue reference and constraints>"
$acme-recipe-03-breakdown-github-issue context="<approved analysis>"
$acme-recipe-04-implement-github-issue context="<approved work item and base branch>"
```

Use phases 07 and 08 only after explicit authorization to publish remote branches or pull requests. For the
recipe format, worklog pattern and full command/phase map, read [github-issue-workflow.md](github-issue-workflow.md).

## Adapt the boilerplate

Replace `acme-` in directory names, frontmatter, recipe names, `uses` references and invocation examples as
one change. Then specialize the generic phase command into commands such as issue analysis, stack preparation,
implementation and verification while keeping their contracts direct and reusable. See the
[authoring guide](../../docs/authoring.md) for the command and recipe contracts.
