# Recover the valid prefix of a previous run

This example connects the [Acme command/recipe catalog](../acme/README.md) to the core recovery API.
A review command succeeds and the reporting command fails.
A new run can reuse the review result only if it is still compatible and valid.
Recovery never changes the failed result into success or selects isolated results after an invalid step.

## Run the isolated demonstration

From an engine checkout with its Python environment installed:

```sh
.venv/bin/python examples/recovery/demo.py
.venv/bin/python examples/recovery/demo.py --invalidate-review
```

The demo creates and removes a temporary Git repository. It uses real catalog validation, planning,
the local check script, recovery and `recipe advance`. Review/report results and dependency evidence are
**synthetic fixtures**. No AI CLI, model request, real review, test suite or application session runs.

| Case | Recovered steps | Next step |
|---|---|---|
| Unchanged fixture | `review` | `report` |
| Changed review dependency | None | `review` |

Both cases verify that the previous state stays byte-for-byte unchanged. Temporary artifacts are removed
on exit. The evidence shortcuts inside the demo must not be copied into a real recovery procedure.

## Recover a real run

Install Acme as described in its README. The coordinator must
have retained the original complete plan and ordered results as `previous/state.json`, plus failure
diagnostics and the historical evidence necessary to establish validity. Missing evidence means no reuse.
Run from the same application root, with the same adapter, profile and functional inputs:

```sh
# These files are new; choose unused names and preserve all previous run artifacts.
.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-reviewed-change \
  --adapter codex --input target=HEAD --input focus=correctness > new-plan.json
.ai-evo/bin/ai-evo-skills recipe recover \
  --source-state previous/state.json --plan new-plan.json --inspect > evidence.json
```

All checks start with `valid: false`. Before changing any check, compare the recorded review's actual
dependencies with current state: the resolved target commit, relevant tracked contents, review scope and
directives. A symbolic name such as `HEAD` alone is insufficient. Fill `checked_at`, `reason`, and matching historical/current
dependency fingerprint maps only when supported by evidence. The core binds checks to plans and outputs,
but does not inspect Git or determine semantic freshness on your behalf.

```sh
.ai-evo/bin/ai-evo-skills recipe recover \
  --source-state previous/state.json --plan new-plan.json \
  --evidence evidence.json --output-dir new-runtime
.ai-evo/bin/ai-evo-skills recipe advance < new-runtime/state.json
```

`new-runtime` must not exist and must be outside the source runtime directory. Read `recovery.json` for
provenance and the stop reason, and continue the ordinary coordinator loop using the new `state.json`.
Do not reinitialize its results. A changed command, policy, executor, input or unchecked dependency stops
reuse before the affected step. A failed or skipped source step also ends the recoverable prefix.

Acme does not have a `recover_from_session` input: that convenience belongs to catalog integrations,
not the generic recipe schema. Core recovery writes runtime state and provenance; it does not recreate
worklogs, replay side effects, reset Git, or restore branches. A catalog with external bookkeeping must
verify and rebuild it before exposing the new state for execution. Use `--session-parameter` only for an
explicit bookkeeping input, never to ignore a functional difference; Acme needs no rebinding.

See [the recovery contract](../../docs/execution.md#recovering-a-verified-recipe-prefix).
