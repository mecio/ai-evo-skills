# Authoring commands, recipes and profiles

[Back to the README](../README.md)

Start with the [first skill walkthrough](first-skill.md#create-your-first-skill), then use this reference
when extending the catalog. Keep the generated planning and handoff instructions when replacing task prompts.

## Create artifacts

```bash
./.ai-evo/bin/ai-evo-skills create command review
./.ai-evo/bin/ai-evo-skills create recipe reviewed-change
./.ai-evo/bin/ai-evo-skills create recipe team-review --catalog
./.ai-evo/bin/ai-evo-skills create effort-profile careful
```

Commands are always created in the shared catalog. Recipes default to the local, Git-ignored
`skills/custom/recipes`; `--catalog` makes them shared. Templates live under `.ai-evo/templates/`, organized by
artifact type. Generated `TODO` markers must be completed before validation and synchronization can succeed.
Creation validates project integration, storage and reserved names, but allows incomplete draft content.
You can create several commands, recipes and profiles before completing them. All generated YAML is parsable;
`validate`, `sync` and planners still reject unresolved TODOs and invalid contracts.
Examples under `.ai-evo/examples/` are documentation and are never installed by `init`.

Recipe names must be `<namespace>-recipe-<name>` in both collections; directory names, `SKILL.md` frontmatter,
`recipe.yaml` and references to nested recipes must agree. New commands use `<namespace>-cmd-<name>`
consistently in the directory, frontmatter, planning instructions and invocations. The complete skill name
must fit within 64 characters, including its marker.

Pass short names to `create`; it adds the namespace and the `cmd-` or `recipe-` marker.
For commands, `create command review` produces `<namespace>-cmd-review`. Already prefixed names such as
`cmd-review` or `<namespace>-cmd-review` are rejected; pass `review`. Existing commands with legacy names
remain valid. To rename one, update its directory, frontmatter, planning instructions, invocations and recipe
`uses` references, then run `validate` and `sync`. See the
[naming rules and migration guide](recipe-naming-migration.md) for rejected forms and existing recipes.

## Command contract

Every command directory contains only `SKILL.md`. It uses Agent Skills frontmatter plus one formal interface:

```yaml ai-evo-interface
executor: claude
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  target:
    description: Git branch, commit or diff to inspect.
    required: true
  focus:
    description: Area that deserves particular attention.
    default: general
```

Every input must declare a non-empty description and exactly one of `required: true` or a string `default`.
Unknown, duplicate and missing required inputs stop planning. Invocation uses `key=value`; quote values that
contain spaces.

Execution restrictions and native prompt delivery are described in the [execution reference](execution.md).

## Recipe contract

A recipe directory contains `SKILL.md` for its purpose, coordinator procedure and expected result, plus
`recipe.yaml` for its formal inputs, executor, ordered steps and output. Start with the generated template
and the [review/verification illustration](first-skill.md#compose-skills-into-recipes).

Recipe inputs follow the same description and required/default rules as command inputs. Each step has a unique
`id`, a `uses` reference to a command or recipe, and a `with` mapping matching that child's inputs.
`${{ inputs.name }}` reads a recipe input; `${{ steps.id.output }}` reads an earlier step's output.
Recipes form a directed acyclic graph and execute in declared sequence. Unknown skills, unknown inputs,
forward references, duplicate step ids and direct or indirect cycles are validation errors.
`outputs.result.value` is the single public recipe result.

Steps may declare `when` to compare an input or earlier result with a literal string. Equality is exact by
default; optional `normalize: trim` tolerates outer whitespace without changing the recorded output.
All branches are validated before execution, including branches that will be skipped. Keep the generated
`recipe advance` coordinator loop to resolve outputs and evaluate conditions. The [runtime protocol](recipe-runtime.md)
defines the condition syntax, typed placeholders, nested recipes and skipped results.

## Effort profiles

`--ai-effort-profile=<name>` selects one complete profile for a command or entire recipe. When omitted, the
planner uses `<namespace>-default`. Profiles are isolated: they do not inherit from one another.

| Parameter | Values | Purpose |
|---|---|---|
| `reasoning.level` | `low`, `medium`, `high` | Requested reasoning depth |
| `resources.subagents` | `disabled`, `enabled`, `auto` | Whether delegated subagents may be used |
| `resources.network` | `disabled`, `enabled`, `auto` | Network resource preference; command policy may be stricter |
| `execution.concurrent-on-same-worktree` | boolean | Whether concurrent work may share one checkout |
| `execution.reuse-session` | `never`, `correction-only`, `always` | When a delegated session may be resumed |
| `output.delivery` | `final-only`, `streaming` | Final-only or intermediate output delivery |
| `output.verbose-logs` | `full`, `summarize`, `errors-only` | Amount of command and tool output reported |
| `tests.strategy` | `minimal`, `necessary`, `full` | Expected breadth of verification |
| `tests.repeat-passed` | boolean | Whether unchanged successful tests may run again |
| `context.repeat-readable-content` | boolean | Whether worktree content may be copied into prompts |
| `context.repository-exploration` | `targeted`, `auto`, `exhaustive` | Breadth of repository exploration |
| `report.profile-application` | `none`, `summary`, `full` | Amount of profile detail reported |

Here, `auto` leaves the resource decision to the executing AI. Effort profiles express resource and reporting
strategy; command execution policies express mandatory restrictions.
