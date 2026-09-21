# Authoring commands, recipes and profiles

[Back to the README](../README.md)

Start with the [first skill walkthrough](first-skill.md#create-your-first-skill), then use this reference
when extending the catalog. Keep the generated planning and handoff instructions when replacing task prompts.

## Create artifacts

```bash
./.ai-evo/bin/ai-evo-skills create command review
./.ai-evo/bin/ai-evo-skills create step approval
./.ai-evo/bin/ai-evo-skills create recipe reviewed-change
./.ai-evo/bin/ai-evo-skills create recipe team-review --catalog
./.ai-evo/bin/ai-evo-skills create effort-profile careful
```

Commands and steps are always created in the shared catalog. `create command` writes to
`skills/catalog/commands`; `create step` writes to `skills/catalog/recipes/_steps`. Commands are directly
invocable, while steps are atomic services available only through recipes and are not published to native
skill directories. Recipes default to the local, Git-ignored `skills/custom/recipes`; `--catalog` creates a
directly invocable shared recipe under `skills/catalog/recipes`. Templates live under `.ai-evo/templates/`,
organized by artifact type. Generated `TODO` markers must be completed before validation and synchronization can succeed.
Creation validates project integration, storage and reserved names, but allows incomplete draft content.
You can create several commands, recipes and profiles before completing them. All generated YAML is parsable;
`validate`, `sync` and planners still reject unresolved TODOs and invalid contracts.
Examples under `.ai-evo/examples/` are documentation and are never installed by `init`.

Recipe names must be `<namespace>-recipe-<name>` in public, iteration and personal collections; directory
names, `SKILL.md` frontmatter, `recipe.yaml` and references to nested recipes must agree. New commands use
`<namespace>-cmd-<name>` and new steps use `<namespace>-step-<name>` consistently in their directory and
frontmatter. The complete skill name must fit within 64 characters, including its marker.

Pass short names to `create`; it adds the namespace and the `cmd-`, `step-` or `recipe-` marker.
For commands, `create command review` produces `<namespace>-cmd-review`. Already prefixed names such as
`cmd-review` or `<namespace>-cmd-review` are rejected; pass `review`. Existing commands with legacy names
remain valid. To rename one, update its directory, frontmatter, planning instructions, invocations and recipe
`uses` references, then run `validate` and `sync`. See the
[naming rules and migration guide](recipe-naming-migration.md) for rejected forms and existing recipes.

## Command contract

Every command directory contains `SKILL.md` and may contain `references/` for documents and output schemas. It uses Agent Skills frontmatter plus one formal interface:

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

Commands always use the invoking AI. Their interfaces contain `inputs`, `execution-policy` and optionally `output-schema`;
an `executor` field is invalid, including `executor: current`. Choose another executor only on a recipe
step to reuse the same command with different AIs.

Execution restrictions and native prompt delivery are described in the [execution reference](execution.md).

## Step contract

A step has the same formal interface and execution policy as a command, but lives under
`skills/catalog/recipes/_steps`, declares `ai-evo-kind: step` and `ai-evo-recipe-only: true`, and uses an
`<namespace>-step-<name>` name. A command must instead declare `ai-evo-recipe-only: false`.

Steps can appear in a recipe's `uses` field and are planned with that recipe. `command plan` rejects them and
`sync` does not publish them as directly invocable native skills. Use a step for approval preparation, worklog
management and gates whose meaning depends on outputs from other recipe calls.

> [!TIP]
> A useful way to recognize a step is to count its upstream results. If an operation requires outputs produced
> by two or more earlier commands or steps, model it as a recipe-only step. The recipe is responsible for
> coordinating those results and passing them together. Keep it as a command when direct invocation remains
> meaningful and it depends on at most one earlier operation.

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
`recipe.yaml` for its formal inputs, ordered steps and output. It may also contain a real `references/` directory
with supporting documents that the coordinator reads only when the recipe procedure calls for them. Reference
entries may be regular files or directories and may not be symbolic links. Other recipe-local files and
directories remain invalid. Start with the generated template and the
[review, verification and revision example](first-skill.md#compose-skills-into-recipes).

Recipe inputs follow the same description and required/default rules as command inputs. Each step has a unique
`id`, a `uses` reference to a command, step or recipe, and a `with` mapping matching that child's inputs.
`${{ inputs.name }}` reads a recipe input; `${{ steps.id.output }}` reads an earlier step's output.
Recipes form a directed acyclic graph and execute in declared sequence. Unknown skills, unknown inputs,
forward references, duplicate step ids and direct or indirect cycles are validation errors.
`outputs.result.value` is the single public recipe result.

Store a recipe under `skills/catalog/recipes/_iterations/<recipe-name>` when it represents a technical unit
consumed by another recipe and its inputs do not form a useful direct invocation. The engine validates and
expands these recipes through `uses`, but rejects them as root plans and does not publish them to native skill
directories. Their directory still contains the same `SKILL.md`, `recipe.yaml` and optional `references/`
contract as other recipes.

There is no separate `create iteration` command. Create the recipe with `create recipe <name> --catalog`, then
move its complete directory from `skills/catalog/recipes/<recipe-name>` into
`skills/catalog/recipes/_iterations/<recipe-name>` before other recipes reference it. Keep the recipe name
unchanged. Run `validate` after the move; `sync --dry-run` should omit both `_iterations` recipes and `_steps`.

The two underscore directories are reserved collections:

| Collection | Kind | Root planning | Native publication |
|---|---|---|---|
| `recipes/<recipe-name>` | Shared recipe entrypoint | Allowed | Published |
| `recipes/_iterations/<recipe-name>` | Nested technical recipe | Rejected | Not published |
| `recipes/_steps/<step-name>` | Atomic recipe-only step | Rejected | Not published |
| `custom/recipes/<recipe-name>` | Personal recipe entrypoint | Allowed | Published locally |

### Executor selection

A directly invocable recipe always uses the invoking AI as its coordinator and is published to every enabled
AI. A top-level `executor` field is invalid, including `executor: current`. Each step may declare a literal
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

### Sequential iteration

A recipe may invoke a child recipe once for every item in a JSON array produced by an input or an earlier
step. Declare `for_each.items` on the child recipe call and map the complete current item with `${{ item }}`:

```yaml
steps:
  - id: discover
    uses: acme-cmd-discover-work
  - id: implement
    uses: acme-recipe-implement-work
    for_each:
      items: "${{ steps.discover.output }}"
    with:
      work_item: "${{ item }}"
```

`for_each` accepts only a complete reference and may invoke only a recipe. The referenced value must resolve
at runtime to a JSON array. Items run in array order and each child recipe completes before the next begins.
String items are passed unchanged; every other JSON item is passed as canonical compact JSON. The loop output
is a JSON array containing each child recipe result in the same order. An empty array produces `[]` without
running the child. `when` cannot be combined with `for_each`, and nested `for_each` is not supported.

Use iteration when the number of work items is known only after an analysis step. Keep a fixed sequence as
ordinary recipe steps when its size is known while authoring.

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

### Project capabilities for fixed local operations

A project can declare `skills/config/execution-capabilities.yaml` (schema:
`schemas/project-capabilities.schema.json`). Capability names must use the project
namespace. Each entry names an executable basename under `.ai-evo-prj/scripts`,
a fixed operation, whether arguments are accepted, and supported workspace modes:

```yaml
version: '1.0'
capabilities:
  acme.local-commit:
    script: acme-git-local
    operation: commit
    arguments: true
    workspaces: [read-write]
```

A command requires it through `execution-policy.capabilities`. The Claude adapter
constructs a scoped Bash allow rule for that operation; it never grants generic
Bash. The project script must validate data arguments and perform only the declared
operation without accepting arbitrary commands. Missing executables, unsupported
adapters, incompatible workspace modes and conflicting denies fail planning.
Adapter policy baselines incorporate these grants; profile and invocation ceilings
remain restrictive.

Use a hybrid policy: recipe instructions define the authorized objective and
local-only writes, capabilities grant required operations, and
`deny-capabilities: [git.remote-write, github.remote-write]` veto known publication
and remote mutation commands. Denies take precedence. These mappings are command
patterns, not a network firewall or an exhaustive classification of remote writes.
Authorized scripts and configured Git hooks remain trusted code. Remote reads can
use the dedicated read capabilities without authorizing remote writes.
