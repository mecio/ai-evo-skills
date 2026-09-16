---
name: acme-recipe-test-legacy-and-unit
description: "Detect the PHP context with a script, run legacy tests and applicable Unit tests, then report their results."
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Test the suites applicable to this worktree

## Purpose

Detect the PHP context with a script, run legacy tests and applicable Unit tests, then report their results.

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-test-legacy-and-unit` with the current adapter, the received
   inputs and the optional `--ai-effort-profile`.
2. Keep the complete plan and an initially empty ordered `results` array. Before each step, send
   `{"plan": <complete plan>, "results": <recorded results>}` as JSON on stdin to
   `.ai-evo/bin/ai-evo-skills recipe advance`. The core resolves typed output references and evaluates `when`
   using exact string equality and any explicit `normalize: trim`; never alter recorded output or evaluate conditions yourself.
3. On `skipped`, append the returned `result` unchanged and continue without invoking the command.
   On `ready`, execute only the returned `step`: send it to `.ai-evo/bin/ai-evo-skills command execute` on stdin
   for delegated mode, or apply its resolved handoff directly for current mode. Do not replan children.
4. Before recording success for `php_context`, require its output with outer whitespace trimmed to be exactly
   `php72` or `php83`. Any other detector output is a task failure: record it as failed with exit code 1
   and stop. Preserve valid output unchanged in the journal. Record success as
   `{"step": "<id>", "status": "succeeded", "output": "<complete output>"}`. Preserve whitespace. A skipped upstream output is passed to command inputs as JSON text describing the skip;
   the reporting command must describe that state as a skipped suite, never as a passing suite.
5. On failure, record `{"step": "<id>", "status": "failed", "exit_code": <nonzero code>}` and stop.
   A script or test failure reported by the command is a task failure even if the native AI CLI exits 0;
   use the reported nonzero code when available, otherwise 1.
   Never execute later steps after a failure or a runtime validation error. A skip is not a failure.
6. Repeat `recipe advance` until `complete`, then return its `output` unchanged, including a structured
   skipped result if the recipe's final output names a skipped step. Read `.ai-evo/docs/recipe-runtime.md`
   for the full protocol, including nested recipe conditions.

## Expected output

A Markdown report with the legacy test result and the Unit result or its context-based skip.
The recipe stops at the first failure; it does not produce a final aggregate report after a failed suite.

## Constraints

- Keep the script and runner steps on Codex with the bundled restrictive policies.
- Use recipe advance to evaluate conditions and preserve skip records.
- Stop on invalid context, unavailable runners or failed tests.

## Success criteria

- Legacy tests run in either configured context; Unit tests run only in php83.
- An unknown context fails before any suite runs.
- The report preserves actual suite outcomes and marks inapplicable work as skipped.

## Examples

```text
$acme-recipe-test-legacy-and-unit
/acme-recipe-test-legacy-and-unit
```
