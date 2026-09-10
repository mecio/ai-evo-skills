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
2. Read and execute each returned command `SKILL.md` in plan order. Before executing a step, replace every
   `ai-evo-step-output` reference with the complete output produced by the referenced earlier step.
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
