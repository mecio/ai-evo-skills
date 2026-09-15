# From a reusable prompt to your first skill

[Back to the README](../README.md)

This walkthrough installs the engine, publishes a complete review skill, and shows how to reuse it in recipes.
Use `acme` as the example namespace and run shell commands from the application repository after initialization.
Check the [requirements](../README.md#requirements) before starting.

To start from complete files, use the [Acme boilerplate](../examples/acme/README.md): three commands and two
recipes, including a conditional security review. This walkthrough explains how to author the pieces yourself.

## Install and initialize

Choose a tag from [GitHub Releases](https://github.com/mecio/ai-evo-skills/releases), preferring a stable release
when available. Read the selected release's notes and README. Replace `<release-tag>` with its exact tag,
then link the engine from an existing application Git repository:

```bash
git clone --branch '<release-tag>' https://github.com/mecio/ai-evo-skills /chosen/path/ai-evo-skills
cd /path/to/project
ln -s /chosen/path/ai-evo-skills .ai-evo
uv sync --frozen --project .ai-evo
./.ai-evo/bin/ai-evo-skills init --namespace acme --adapter codex --adapter claude
```

Enable only the adapters you use. The namespace must contain 3–6 lowercase ASCII letters; all examples below
use `acme`. `init` creates `.ai-evo-prj`, project configuration and missing client entrypoints. Existing
`AGENTS.md` or `CLAUDE.md` files must already reference `.ai-evo-prj/entrypoint.md`; initialization checks them
and preserves their contents.

Put shared project guidance in `.ai-evo-prj/entrypoint.md` and its directives. For an external specification
repository, create the `.ai-evo-prj` symlink before `init`. See [project setup](project-setup.md) for the
full layout, shared worktrees and publication settings.

## Create your first skill

Suppose your team repeatedly asks for a review of a Git diff, with findings supported by file and line
references. Store that prompt once as a command:

```bash
./.ai-evo/bin/ai-evo-skills create command review
```

Open `.ai-evo-prj/skills/catalog/commands/acme-cmd-review/SKILL.md` and replace its generated draft with this complete
example. **Purpose**, the review steps in **Procedure**, and **Expected output** capture the reusable prompt;
**Interface** declares what changes between invocations. The first procedure steps preserve the engine handoff.

````markdown
---
name: acme-cmd-review
description: Review a Git diff without modifying files and report actionable findings with evidence.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Review a Git diff

## Purpose

Find actionable regressions in tracked changes relative to a Git target, using the team's review criteria.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  target:
    description: Local Git commit or ref to compare with the tracked working tree.
    required: true
  focus:
    description: Review area to emphasize, such as correctness or security.
    default: correctness
```

## Procedure

1. If an `ai-evo-execution-handoff` is supplied, use its resolved inputs, working directory, policy and
   profile instructions; continue at step 4 without planning again.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan acme-cmd-review` with `--adapter` set to the current
   adapter, each received input passed as `--input key=value`, and any requested `--ai-effort-profile`.
   Stop if planning or validation fails.
3. Pass the complete resolved plan JSON to `.ai-evo/bin/ai-evo-skills command execute` on stdin.
   Return its output and stop; the delegated AI performs the review below.
4. Read `.ai-evo-prj/entrypoint.md` and the project directives relevant to the changed files and focus.
5. Use `.ai-evo/bin/ai-evo-git-read rev-parse "<target>"` to resolve the supplied target to a commit;
   replace the placeholder with the input value and stop if resolution fails. Use the same wrapper's
   `status` and `diff "<resolved-commit>"` operations to inspect the tracked changes. Follow the resolved
   policy instructions for all reads.
6. Check the changed code and directly affected callers for regressions, emphasizing `focus`.
   Report only findings supported by concrete evidence. Mention untracked files as outside this review.
7. Return the report below. State any verification limits; do not run checks that require writes or network.

## Expected output

A Markdown report identifying the target and focus, with findings ordered by priority. Each finding includes
file and line references, its impact and supporting evidence. If none are found, say so and list review limits.

## Constraints

- Do not modify files or access the network.
- Keep exploration focused on the diff and its relevant dependencies.

## Success criteria

- Every reported finding is supported by the inspected code.
- The report distinguishes completed checks from limitations and leaves the working tree unchanged.

## Examples

```text
$acme-cmd-review target=HEAD focus=security
/acme-cmd-review target=HEAD focus=security
```
````

Validate the completed skill, preview publication, then synchronize it:

```bash
./.ai-evo/bin/ai-evo-skills validate
./.ai-evo/bin/ai-evo-skills sync --dry-run
./.ai-evo/bin/ai-evo-skills sync
```

In a client session opened in the application repository, invoke it with:

| Client | Invocation |
|---|---|
| Codex | `$acme-cmd-review target=HEAD focus=security` |
| Claude Code | `/acme-cmd-review target=HEAD focus=security` |

`HEAD` reviews staged and unstaged tracked changes against the latest commit. Use another local ref to change
the comparison. Next time, invoke the same skill with new inputs; its review instructions remain in the catalog.
Update that source when the team's prompt improves, then validate and synchronize again.

### Shorter invocations with fixed choices

> [!TIP]
> Put recurring choices in the skill or recipe so callers can omit them. In the command's interface or a
> recipe's `inputs`, replace `target`'s `required: true` with `default: HEAD` and set `focus` to
> `default: security`. With these defaults, `$acme-cmd-review` is enough; explicit inputs can still override them.
>
> For a fixed specialization, a recipe can pass literal `target: HEAD` and `focus: security` in a step's
> `with` mapping to a command or nested recipe that accepts those inputs, without exposing them as recipe
> inputs. A specialized command can instead state those fixed choices in its procedure and omit the
> corresponding inputs from its interface.
>
> Give the variant a descriptive name, such as `acme-cmd-review-security` or `acme-recipe-review-security-head`,
> so its invocation communicates the built-in choices. The name describes the behavior; the defaults,
> mappings or instructions implement it. Keep the artifact name and its references consistent when renaming.
>
> For example, create a recipe with `create recipe review-security-head --catalog`, complete its generated
> `SKILL.md`, and use this `recipe.yaml` to reuse the `acme-cmd-review` command above:
>
> ```yaml
> version: "1.0"
> name: acme-recipe-review-security-head
> inputs: {}
> steps:
>   - id: review
>     uses: acme-cmd-review
>     with:
>       target: HEAD
>       focus: security
> outputs:
>   result:
>     value: "${{ steps.review.output }}"
> ```
>
> After `validate` and `sync`, invoke `$acme-recipe-review-security-head` in Codex or
> `/acme-recipe-review-security-head` in Claude Code. Both choices are already stored in the recipe;
> callers supply no parameters and the review prompt stays in the shared command.

## Compose skills into recipes

A recipe reuses command prompts and passes results between steps. For example, a review command can run in
Claude and a verification command in Codex, while Codex coordinates the sequence.

```bash
./.ai-evo/bin/ai-evo-skills create recipe reviewed-change --catalog
```

This creates `acme-recipe-reviewed-change` with a `SKILL.md` and `recipe.yaml`. Complete the generated
`SKILL.md` descriptions while preserving its coordinator procedure. The following illustrative `recipe.yaml`
assumes two completed shared commands: `acme-cmd-review`, accepting `target`, and
`acme-cmd-verify`, accepting `target` and the previous `review`. Leave their executors unset and enable both
adapters. The recipe chooses the executor for each call.

```yaml
version: "1.0"
name: acme-recipe-reviewed-change
inputs:
  target:
    description: Local Git commit or ref to compare with the tracked working tree.
    required: true
steps:
  - id: review
    uses: acme-cmd-review
    executor: claude
    with:
      target: "${{ inputs.target }}"
  - id: verify
    uses: acme-cmd-verify
    executor: codex
    with:
      target: "${{ inputs.target }}"
      review: "${{ steps.review.output }}"
outputs:
  result:
    value: "${{ steps.verify.output }}"
```

The verification prompt should check each finding against the diff, discard unsupported claims and return a
final report. After completing both commands and the recipe, run `validate` and `sync`, then invoke
`$acme-recipe-reviewed-change target=HEAD` in Codex or `/acme-recipe-reviewed-change target=HEAD` in Claude.
The invoking AI coordinates both calls. The second step receives the first report automatically.
Steps run in declared order and stop on failure; forward references and dependency cycles are rejected.

Without `--catalog`, recipes are created under `skills/custom/recipes` and ignored by Git. Commands always
belong to the shared catalog. Recipe names use `<namespace>-recipe-<name>`; command names use
`<namespace>-cmd-<name>`. Pass only the short name to `create`. See [authoring](authoring.md) for contracts,
effort profiles and draft completion, and [recipe naming migration](recipe-naming-migration.md) for older catalogs.
