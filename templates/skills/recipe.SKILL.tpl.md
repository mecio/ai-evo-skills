---
name: <namespace>-<skill-name>
description: TODO: explain when the AI must use this recipe and what final result it produces.
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
2. Process returned steps in plan order. Replace each `ai-evo-step-output` reference in `with` with the complete
   output of the earlier step. For delegated steps, send the complete resolved step JSON to
   `.ai-evo/bin/ai-evo-skills command execute` on stdin. The core supplies the execution handoff; do not replan
   children or ask delegated executors to invoke the planner. For current-mode steps, apply the resolved
   handoff directly.
3. Stop on the first failed step and return the declared recipe result.

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
