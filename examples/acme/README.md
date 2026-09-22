# Acme starter catalog

A complete boilerplate with three commands and two recipes. Copy it into an initialized project to try
shared prompts, input defaults, a direct recipe and an advanced conditional recipe. All skills use the `acme`
namespace and work with either bundled adapter. `init` does not install this catalog automatically.

## What is included?

| Artifact | Purpose |
|---|---|
| [acme-cmd-detect-changes](catalog/commands/acme-cmd-detect-changes/SKILL.md) | Compare tracked working-tree content with a local Git target; return `changed` or `clean`. |
| [acme-cmd-review](catalog/commands/acme-cmd-review/SKILL.md) | Review the diff using a requested focus and report findings with evidence. |
| [acme-cmd-report-review](catalog/commands/acme-cmd-report-review/SKILL.md) | Summarize a supplied review, preserving findings, limits and skipped status. |
| [acme-recipe-reviewed-change](catalog/recipes/acme-recipe-reviewed-change/recipe.yaml) | Direct review followed by reporting. |
| [acme-recipe-review-security-if-changed](catalog/recipes/acme-recipe-review-security-if-changed/recipe.yaml) | Advanced conditional security review. |

The internal step is not published as a directly invocable skill; `command plan` rejects direct calls.
Its helper needs Python 3.11+. It runs directly under the coordinator's permissions using `executor: current`,
with temporary-file writes only. It grants no additional permissions to a delegated client.

Both recipes reuse the same review and reporting commands. Each recipe directory also contains a complete
`SKILL.md` with the coordinator procedure. The catalog has no draft placeholders.

## Copy into a project

Use an engine checkout that contains this example and supports conditional recipes with `normalize: trim`.
Follow the [installation guide](../../docs/first-skill.md#install-and-initialize), initializing with namespace
`acme` and at least one of `codex` or `claude`. Run the following from that application repository, using a
fresh catalog with none of these six names already present:

```bash
cp -R .ai-evo/examples/acme/catalog/commands/. .ai-evo-prj/skills/catalog/commands/
cp -R .ai-evo/examples/acme/catalog/recipes/. .ai-evo-prj/skills/catalog/recipes/
./.ai-evo/bin/ai-evo-skills validate
./.ai-evo/bin/ai-evo-skills sync --dry-run
./.ai-evo/bin/ai-evo-skills sync
```

If you already created `acme-cmd-review` from the tutorial, choose which implementation to keep before copying;
the copy commands overwrite matching files. This boilerplate gives `target` a `HEAD` default so the recipes
and review command can be invoked without arguments. It reuses the default effort profile created by `init`.

For another namespace, replace `acme-` consistently in directory names, frontmatter, planner instructions,
recipe names, `uses` references and invocation examples before validation. See the
[authoring guide](../../docs/authoring.md) for naming and input contracts.

## Try it

Open your AI client in the application repository. In Codex:

```text
$acme-cmd-review
$acme-recipe-reviewed-change
$acme-recipe-review-security-if-changed
```

In Claude Code, replace the leading `$` with `/`. Each line is a separate invocation. Native AI execution
requires an authenticated CLI and makes model requests.

The ordinary recipe defaults to `target=HEAD` and `focus=correctness`; both can be overridden:

```text
$acme-recipe-reviewed-change target=main focus=security
```

The conditional recipe exposes only `target`, defaulting to `HEAD`. It fixes `focus: security` internally,
as communicated by its name. To compare against another existing local ref:

```text
$acme-recipe-review-security-if-changed target=main
```

## How the condition behaves

| Detector outcome | Review step | Report step |
|---|---|---|
| `changed` | Runs with `focus: security`. | Summarizes the review and its limits. |
| `clean` | Skipped by `recipe advance`. | Explains that no review ran because the tracked diff was empty. |
| Inspection failure or invalid token | Workflow stops. | Does not run. |

`normalize: trim` permits outer whitespace such as `changed\n`; successful detector output is otherwise
limited to `changed` or `clean`. The recipe's coordinator instructions require invalid tokens to be recorded
as failures. The core then evaluates `when` and passes a skipped review to the report command as JSON text
with `type: ai-evo-step-skipped`. The report must not describe skipped work as a passed review.

The comparison uses tracked working-tree content against the chosen target. Untracked files and submodules
are outside its scope. With `HEAD`, a clean tracked diff skips the conditional review; a tracked edit enables
it. A missing target, including `HEAD` in a repository without commits, is an inspection failure.

Commands request read-only workspace access and disabled network access. The detector and review use the
bundled Git read wrapper; reporting consumes the prior output without repeating inspection. Keep the worktree
stable during a run so detection and review see the same changes. This example demonstrates conditional AI
orchestration; the prompts and reports remain tasks performed by the AI.

For the full condition and journal semantics, see the [recipe runtime guide](../../docs/recipe-runtime.md).

## Extend the pattern with project scripts

The [runtime-tests catalog](../runtime-tests/README.md) adapts an Enabu workflow: detect the configured PHP
context with a script, run legacy tests, conditionally run Unit tests and report the results. Its names do
not collide with this catalog. It includes a runnable context helper and requires your real test wrappers
and worktree configuration before executing suites.

That example assigns script-backed steps to Codex because the bundled restricted Claude policy permits
only the Git read wrapper used above. See [command scripts](../../docs/command-scripts.md) for deterministic
output contracts and an inventory of other workflows, including branch planning and commit validation.

## Recover a previous run

Follow the [recovery example](../recovery/README.md) to retain a verified consecutive prefix in a new runtime.
It includes an isolated demo without model requests and the separate procedure for real dependency checks.
The original run remains intact; results after the first invalid step are never cherry-picked.
