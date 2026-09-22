---
name: acme-recipe-reviewed-change
description: "Review tracked changes and summarize its findings with two direct commands."
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Review and report

## Purpose

Run a tracked-change review and summarize its findings in sequence. This is the default direct-recipe pattern.

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-reviewed-change` with the current adapter, the received
   inputs and the optional `--ai-effort-profile`.
2. Keep the complete plan and an initially empty ordered `results` array. Before each step, send
   `{"plan": <complete plan>, "results": <recorded results>}` as JSON on stdin to
   `.ai-evo/bin/ai-evo-skills recipe advance`. The core resolves typed output references and evaluates `when`
   using exact string equality and any explicit `normalize: trim`; never alter recorded output or evaluate conditions yourself.
3. On `skipped`, append the returned `result` unchanged and continue without invoking the command.
   On `ready`, execute only the returned `step`: send it to `.ai-evo/bin/ai-evo-skills command execute` on stdin
   for delegated mode, or apply its resolved handoff directly for current mode. Do not replan children.
4. Record success as `{"step": "<id>", "status": "succeeded", "output": "<complete output>"}`. Preserve
   whitespace. A skipped upstream output is passed to command inputs as JSON text describing the skip;
   the reporting command must describe that state as a skipped review, never as a completed review.
5. On failure, record `{"step": "<id>", "status": "failed", "exit_code": <nonzero code>}` and stop.
   Never execute later steps after a failure or a runtime validation error. A skip is not a failure.
6. Repeat `recipe advance` until `complete`, then return its `output` unchanged, including a structured
   skipped result if the recipe's final output names a skipped step. Read `.ai-evo/docs/recipe-runtime.md`
   for the full protocol, including nested recipe conditions.
7. For a retry, follow `.ai-evo/examples/recovery/README.md` to build a new plan and verified prefix.
   Continue with the returned state at step 2; do not reset its results or replay recovered steps.
   This example has no `recover_from_session` recipe input or external worklog importer.

## Expected output

The final Markdown report produced by `acme-cmd-report-review`.

## Constraints

- Keep the recipe limited to review and reporting; start a separate recipe for any correction.
- Preserve the review output when passing it to the reporting command.

## Success criteria

- The review completes before reporting starts.
- The final report retains findings and verification limits.

## Examples

```text
$acme-recipe-reviewed-change
/acme-recipe-reviewed-change
```
