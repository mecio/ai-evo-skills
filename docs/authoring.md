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

Commands always use the invoking AI. Their interfaces contain only `inputs` and `execution-policy`;
an `executor` field is invalid, including `executor: current`. Choose another executor only on a recipe
step to reuse the same command with different AIs.

Execution restrictions and native prompt delivery are described in the [execution reference](execution.md).

### Calling project scripts

A command's `Procedure` may invoke a project script for deterministic detection, name generation,
validation or test execution. Store helpers under `.ai-evo-prj/scripts/` or use existing application tools;
keep command directories limited to `SKILL.md`. Document argv/stdin inputs, working directory, dependencies,
stdout format, failure statuses and side effects. Preserve exact tokens or JSON when another step consumes them.

The AI executes the helper under its resolved policy; recipes do not support shell steps. Confirm that the
selected adapter permits the script. The bundled restrictive Claude policies only allow the Git read wrapper,
so the [runtime-tests example](../examples/runtime-tests/README.md) selects Codex for project-script calls.
See [command scripts](command-scripts.md) for output contracts, verification and the Enabu use-case inventory.

## Recipe contract

A recipe directory contains `SKILL.md` for its purpose, coordinator procedure and expected result, plus
`recipe.yaml` for its formal inputs, ordered steps and output. Start with the generated template
and the [review, verification and revision example](first-skill.md#compose-skills-into-recipes).

Recipe inputs follow the same description and required/default rules as command inputs. Each step has a unique
`id`, a `uses` reference to a command or recipe, and a `with` mapping matching that child's inputs.
`${{ inputs.name }}` reads a recipe input; `${{ steps.id.output }}` reads an earlier step's output.
Recipes form a directed acyclic graph and execute in declared sequence. Unknown skills, unknown inputs,
forward references, duplicate step ids and direct or indirect cycles are validation errors.
`outputs.result.value` is the single public recipe result.

### Executor selection

A recipe always uses the invoking AI as its coordinator and is published to every enabled AI. A top-level
`executor` field is invalid, including `executor: current`. Each step may declare a literal
`executor: claude`, `executor: codex`, another installed adapter
ID, or `executor: current`. Executor is metadata, not a command input; input expressions are not accepted.

```yaml
steps:
  - id: review
    uses: acme-cmd-review
    executor: claude
    with:
      target: HEAD
  - id: verify
    uses: acme-cmd-verify
    executor: codex
    with:
      review: "${{ steps.review.output }}"
```

An omitted step executor uses the calling recipe's AI.
For a nested recipe, an explicit adapter selects that call's AI context; steps without their own executor
inherit it, including through further nesting. `current` means the calling recipe's AI context. Overrides
are local to the call and do not affect later sibling steps or standalone invocations. The root coordinator
continues driving the flattened plan; commands assigned to an explicit adapter run through delegated execution.
Command execution policies and the selected effort profile still apply to the resolved adapter.

For a complete Claude → Codex → Claude feedback round, see the
[recipe walkthrough](first-skill.md#compose-skills-into-recipes). It passes Codex's verification output back
to a Claude revision step alongside the original review. Declare each further round as additional steps;
the [runtime protocol](recipe-runtime.md#how-ais-exchange-results) explains how the coordinator supplies
inputs and records outputs.

All referenced executors must be known to the engine, and all adapters reachable from a published recipe
must be enabled, even in skipped branches. Command and recipe publication is independent of step executors.

### Migrating existing executor declarations

Remove `executor` from command interfaces and the top level of `recipe.yaml`. Place any required delegation
on the calling recipe steps. A command invoked directly always uses the invoking AI; recipes likewise have
no fixed coordinator. The validator rejects old declarations without rewriting them. After updating the
catalog, regenerate plans and run `validate` and `sync`. This is an incompatible beta change within protocol `1.0`.

### Conditions

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
