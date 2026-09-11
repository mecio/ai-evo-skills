---
name: <namespace>-<skill-name>
description: "TODO: explain when the AI must use this recipe and what final result it produces."
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# TODO: recipe title

## Purpose

TODO

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills recipe plan <namespace>-<skill-name>` with the current adapter, the received
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
   aggregation commands must interpret that text as an omitted branch, not a successful test result.
5. On failure, record `{"step": "<id>", "status": "failed", "exit_code": <nonzero code>}` and stop.
   Never execute later steps after a failure or a runtime validation error. A skip is not a failure.
6. Repeat `recipe advance` until `complete`, then return its `output` unchanged, including a structured
   skipped result if the recipe's final output names a skipped step. Read `.ai-evo/docs/recipe-runtime.md`
   for the full protocol, including nested recipe conditions.

## Expected output

TODO

## Constraints

- TODO

## Success criteria

- TODO

## Examples

```text
/<namespace>-<skill-name>
```
