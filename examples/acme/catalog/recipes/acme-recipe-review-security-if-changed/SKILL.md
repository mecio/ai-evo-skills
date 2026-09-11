---
name: acme-recipe-review-security-if-changed
description: "Detect tracked changes, review security only when changes exist, and report the completed or skipped review."
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Review security when tracked changes exist

## Purpose

Detect tracked changes, review security only when changes exist, and report the completed or skipped review.

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-review-security-if-changed` with the current adapter, the received
   inputs and the optional `--ai-effort-profile`.
2. Keep the complete plan and an initially empty ordered `results` array. Before each step, send
   `{"plan": <complete plan>, "results": <recorded results>}` as JSON on stdin to
   `.ai-evo/bin/ai-evo-skills recipe advance`. The core resolves typed output references and evaluates `when`
   using exact string equality and any explicit `normalize: trim`; never alter recorded output or evaluate conditions yourself.
3. On `skipped`, append the returned `result` unchanged and continue without invoking the command.
   On `ready`, execute only the returned `step`: send it to `.ai-evo/bin/ai-evo-skills command execute` on stdin
   for delegated mode, or apply its resolved handoff directly for current mode. Do not replan children.
4. Before recording success for `detect`, require its output with outer whitespace trimmed to be exactly
   `changed` or `clean`. Any other detector output is a task failure: record it as failed with exit code 1
   and stop. Preserve valid output unchanged in the journal. Record success as
   `{"step": "<id>", "status": "succeeded", "output": "<complete output>"}`. Preserve whitespace. A skipped upstream output is passed to command inputs as JSON text describing the skip;
   the reporting command must describe that state as a skipped review, never as a completed review.
5. On failure, record `{"step": "<id>", "status": "failed", "exit_code": <nonzero code>}` and stop.
   Never execute later steps after a failure or a runtime validation error. A skip is not a failure.
6. Repeat `recipe advance` until `complete`, then return its `output` unchanged, including a structured
   skipped result if the recipe's final output names a skipped step. Read `.ai-evo/docs/recipe-runtime.md`
   for the full protocol, including nested recipe conditions.

## Expected output

A Markdown report distinguishing a completed security review from a review skipped after a clean diff.

## Constraints

- Keep security as the fixed review focus.
- Use recipe advance to evaluate conditions and preserve skip records.
- Stop on detector or review failure; never report a failed inspection as clean.

## Success criteria

- A changed diff enables the review; a clean diff skips it.
- The reporting step receives the actual review or its structured skip marker.
- Invalid detector output is reported as a failure.

## Examples

```text
$acme-recipe-review-security-if-changed
/acme-recipe-review-security-if-changed
```
