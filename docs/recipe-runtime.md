# Recipe conditions, iteration and runtime protocol

Recipe orchestration remains the coordinator's responsibility. The core supplies deterministic planning,
condition evaluation and transitions; `recipe advance` never starts an AI process. Use the same flow with
Codex or Claude as coordinator. Execution snapshots and journals are trusted local data, not a security boundary.

The runtime supports nested and iterative plans, but they are advanced features. The recommended default is a
direct recipe that reaches one reviewable checkpoint in a few operations. A developer or outer workflow then
starts the next independent recipe with the approved artifact. This limits context drift and makes recovery
local to the failed phase.

Recipe names, including the root `plan.recipe`, must use `<namespace>-recipe-<name>`. Nested `uses` references
name the full recipe; flattened executable steps still refer to atomic commands with their unchanged names.
Migrate legacy recipe names and regenerate snapshots as described in the [migration guide](recipe-naming-migration.md).

Root planning is available for shared recipes stored directly under `skills/catalog/recipes` and for personal
recipes under `skills/custom/recipes`. Recipes under `skills/catalog/recipes/_iterations` are nested-only:
the planner expands them when reached through `uses` but rejects their name as a root plan. Atomic steps under
`skills/catalog/recipes/_steps` follow the same nested-only boundary and are flattened into the resolved plan.
Neither internal collection is published to native client skill directories.

## Input resolvers

A directly invocable recipe can declare an `input-resolver` for deterministic, project-owned recovery of
inputs before `recipe plan` applies required-input checks or defaults. The resolver names a command that
declares exactly one project-script capability; the engine runs that capability's script and operation from
the repository root, passing each mapped recipe input as `--kebab-case-option value`. A `with` value can also
be a non-empty literal, which is passed unchanged; use it for recipe-owned constants such as the name of the
recipe being planned. References to inputs still receive only explicit values, because the resolver precedes
defaults.

```yaml
input-resolver:
  uses: acme-cmd-report-workflow
  with:
    issue: "${{ inputs.issue }}"
    requested_recipe: "acme-recipe-example"
```

The resolver returns a JSON object with `recommended_recipe`, `resolved_inputs` and `missing_inputs`.
The planned recipe must equal `recommended_recipe`. Explicit `--input` values win over `resolved_inputs`,
which win over recipe defaults. If a name remains in `missing_inputs` and was not supplied explicitly,
planning stops naming only those inputs. Resolver commands do not start an AI subprocess.

## How AIs exchange results

The AI where a recipe is invoked remains its coordinator. A step's `executor` selects the AI that performs
that task; the coordinator drives the plan even when successive steps use different executors.
The [review, verification and revision example](first-skill.md#compose-skills-into-recipes) shows a complete
Claude → Codex → Claude recipe.

The exchange follows the same protocol for each step:

1. The coordinator supplies the plan and recorded results to `recipe advance`. The core resolves references
   such as `${{ steps.review.output }}` into the next step's named `with` inputs.
2. For a delegated step, the coordinator sends the resolved step to `command execute`. The executor receives
   a handoff containing the command's skill snapshot, resolved inputs, working directory, execution policy
   and effort profile. It performs that task and returns its output. For current mode, the coordinator
   performs the resolved task directly.
3. The coordinator records a successful step's complete output string in the result journal, preserving
   whitespace. Later steps receive that result only where their inputs reference it; the coordinator must
   not rewrite or summarize the recorded output. To produce feedback or a summary, declare a command step
   that does so and pass its output onward.

The handoff does not automatically include the coordinator's conversation history or every prior result.
For a revision task, explicitly pass both the original report and the feedback it needs. Selecting the same
executor again does not itself establish a shared conversation; session handling follows the separate
[execution policy](execution.md#session-reuse).

Feedback rounds must be represented as subsequent steps with distinct ids and references to earlier outputs.
Conditions can skip declared steps; they do not create new steps or repeat a sequence until an AI approves.
The coordinator loop below advances this declared sequence. Correction after an execution failure follows
the session policy and is separate from a successful review producing feedback for a later revision step.

## Authoring a condition

```yaml
when:
  value: "${{ steps.detect.output }}"
  equals: "changed"
```

`when` is optional and requires `value` and `equals`, with optional `normalize: trim`. `value` must be a complete reference to an
existing recipe input (`${{ inputs.change_state }}`) or the output of a strictly earlier step. `equals` is a literal
string, including the empty string; it is never interpreted as an expression. References in `with`, `when.value`,
`for_each.items` and `outputs.result.value` must each occupy the complete value: partial interpolation such as
`"issue ${{ inputs.issue }}"` is unsupported. No other operators, Boolean expressions, regular expressions or
executable expressions are supported.

By default the comparison is exact equality of decoded Unicode strings. There is no trimming, newline conversion,
case folding or Unicode normalization. `changed`, `changed\n` and ` changed` differ. JSON escape spelling does not
matter: `"changed"` and `"\u0063hanged"` decode to the same string. Preserve complete successful step outputs.

To tolerate client-added outer whitespace, declare normalization explicitly:

```yaml
when:
  value: "${{ steps.detect.output }}"
  normalize: trim
  equals: "changed"
```

`trim` removes leading and trailing Unicode whitespace from the compared value (Python `str.strip()`),
including spaces, tabs, CR and LF. It does not change `equals`, internal whitespace, case or Unicode
normalization. The original output, journal, downstream inputs and final result remain unchanged. Without
`normalize`, comparison retains the exact previous behavior. Other normalization values are rejected during
authoring and runtime validation. Each nested condition applies only its own normalization; skipped states
remain structured and never become strings for comparison.

The Acme example opts into `trim`: both `changed` and the native CLI output `changed\n` enable the security review.
The detector must still return only `changed` or `clean`, without explanations or Markdown fences.

Both `validate` and `recipe plan` check references used by `when`. Strictly earlier output references exclude
self-dependencies, forward dependencies and all step dependency cycles, including cycles mixing `with` and
`when`. Recipe composition cycles remain errors even under a false condition. Every possible child, profile
and configured adapter is validated before producing the plan; false conditions never hide invalid branches.

## Planned representation

Input references are resolved during planning. Output references remain typed objects:

```json
{
  "id": "review",
  "uses": "acme-cmd-review",
  "when": {
    "all": [
      {"value": {"type": "ai-evo-step-output", "step": "detect"}, "normalize": "trim", "equals": "changed"}
    ]
  }
}
```

The actual step also contains `skill_path`, `with`, `application` and `handoff`, as before. Conditional
plans declare `execution.conditions: "exact-equals-v1"`. No step is pruned at planning time, including
conditions already known from inputs. Consumers must support this capability and use `recipe advance`.

Conditions on nested recipe invocations apply to all expanded command descendants. Their `when.all` lists
contain outer conditions followed by inner ones, in evaluation order. All must match. Evaluation short-circuits
at the first false condition, so a skipped outer branch never requires evaluation of its inner conditions.
Flattened ids remain dot-separated (`branch.review`). A nested recipe's output continues to alias its
declared final descendant; a skip marker identifies that actual descendant, not a synthetic container step.

## Sequential `for_each`

An iterative plan declares `execution.iterations: "json-array-sequential-v1"`. The plan keeps one loop node
with an unresolved `for_each.items` value and a child recipe template. `recipe advance` resolves the value
only after all earlier results are present, parses it as a JSON array and materializes one iteration at a time.

Runtime step ids insert the zero-based array index between the loop id and child id, for example
`implement.0.cover` and `implement.1.cover`. These ids are stable across resume because the original plan and
the recorded producer output are immutable. Each materialized command has `${{ item }}` replaced by the
current item: strings remain unchanged and objects, arrays, numbers, booleans and null use canonical compact
JSON with sorted object keys.

Iterations are ordered and fail-fast. Every command in index 0 completes before index 1 starts. A failed
command stops the whole recipe, and the journal cannot contain later iterations. After all items complete,
the loop exposes a compact JSON array of the declared child recipe result for each iteration. Downstream steps
may reference that aggregate through the ordinary `${{ steps.id.output }}` syntax. An empty source array
produces `[]`. A non-array or invalid JSON source is a runtime error.

Version 1 supports a single iteration level. A child recipe expanded by `for_each` cannot contain another
`for_each`, and a loop call cannot also declare `when`.

## Coordinator loop

Keep the unmodified recipe plan and an ordered `results` array, initially empty. Immediately before each
execution, pass this JSON on stdin to `.ai-evo/bin/ai-evo-skills recipe advance`:

```json
{"plan": "<the complete plan object, not a string>", "results": []}
```

The illustrative `plan` string above must be replaced by the actual JSON object. The command returns one
`ai-evo-recipe-transition` object with `version: "1.0"` and one of these statuses:

| Status | Payload | Coordinator action |
|---|---|---|
| `ready` | `step`: resolved command step | Execute only this step, then append its result record. |
| `skipped` | `result`: complete skipped record | Append it unchanged. Invoke no command and continue. |
| `failed` | `result`: first failed record | Stop. No later step may execute. CLI exits 1. |
| `complete` | `output`: recipe result | Return this string or structured skipped state unchanged. |

`ready`, `skipped` and `complete` exit 0. Invalid plans or journals exit 1 with a diagnostic on stderr and
no transition. A false condition is checked before resolving command inputs. For a ready step, the core
resolves every `with` reference and removes the consumed `when`; the authoritative original plan retains it.
Unresolved conditional steps are rejected by `command execute` with an instruction to use `recipe advance`.

For `application.mode: delegated`, send the entire returned step to `command execute` on stdin. For `current`,
perform its resolved handoff directly. Do not replan either kind. Delegated children may not call `recipe advance`.

Successful and failed records have these exact shapes:

```json
{"step": "detect", "status": "succeeded", "output": "complete command output"}
```

```json
{"step": "detect", "status": "failed", "exit_code": 17}
```

Use a nonzero exit code in 1–255; a current-mode failure without a native code can use 1. Stop immediately on
failure. Calling `recipe advance` with that final failed record returns `failed`; adding any later record is
invalid. If correction is attempted under the existing session policy, resolve the failure before advancing
and keep one final outcome per step; the journal is not a retry history.

Journals must be a sequential prefix of planned steps, without duplicates, future results or missing output
fields. Success outputs must be strings; empty strings are valid. Missing or invalid outputs are errors,
never implicitly empty strings or false conditions. A failure or runtime validation error activates fail-fast.

For commands that call scripts, record the command's promised result: an exact token/JSON string or a report
based on the runner's evidence. Script failures must become task failures even if the native AI CLI exits 0.
The core does not validate command-specific token values or JSON fields. See the
[script output contract](command-scripts.md#define-the-script-and-command-contracts) and the
[context-dependent test example](../examples/runtime-tests/README.md).

## Skips and aggregation

A skipped record is generated by the core:

```json
{
  "step": "review",
  "status": "skipped",
  "output": {"type": "ai-evo-step-skipped", "step": "review", "reason": "condition-false"}
}
```

A skip is not a failure. Independent later steps still run. A condition reading a skipped output is false;
it never compares against the textual JSON of the marker. Conditions read prior result states, not the strings
prepared for command arguments. The core checks that recorded skips agree with the original conditions.

An unconditional downstream command may read a skipped output. Since command inputs remain strings, the core
serializes that marker as compact JSON text with sorted keys and no extra whitespace. Successful outputs pass
through unchanged. An aggregation command must explicitly handle this documented marker format as an omitted
branch and must not claim the skipped review completed. There is no implicit empty string, `null` or success result.
The typed journal remains authoritative: a successful command that happens to emit identical JSON is still a
success string in the journal, so aggregators should consume only outputs from commands they trust.

If the recipe's final reference points to a skipped step, `complete.output` is the structured marker itself,
not a JSON string. References to potentially skipped outputs are legal; they use these rules consistently,
including nested recipes. See the complete [Acme example](../examples/acme/README.md).

## Schemas and compatibility

The authoring schema remains `schemas/recipe.schema.json`. Runtime requests are checked against the packaged
`recipe-runtime.schema.json`; the core registers its `planned-step` URN locally, deriving it from
`execution-plan.schema.json` with typed unresolved inputs, optional conditions and current mode. No schema
lookup uses the network. Semantic checks additionally enforce reference ordering, session consistency,
condition and iteration capabilities, journal order and fail-fast.

On-disk protocol `1.0` remains unchanged: `when` is an optional, additive feature and does not itself require
migration. The separate mandatory recipe naming rule does require the migration linked above.
Plans without conditions retain their existing fields and behavior; existing coordinators may
continue their old loop for those plans. Older engines reject `when` under their strict authoring schema;
they cannot safely run conditional recipes. Update the engine and coordinator instructions together when
adopting this capability, available in engine `0.1.0-beta.3`.
`normalize` is another optional extension within this capability. Earlier engines reject that field through
their strict schemas rather than silently ignoring it; they must be updated to use conditions with `trim`.
`for_each` is also additive within protocol `1.0`; iterative plans advertise
`json-array-sequential-v1`. Coordinators must reject that capability unless they drive every transition through
`recipe advance`. Earlier engines reject iterative authoring or runtime plans through their strict schemas.
The release keeps on-disk protocol `1.0`; regenerate execution snapshots when upgrading the engine.
