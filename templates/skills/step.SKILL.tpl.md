---
name: <namespace>-step-<skill-name>
description: "TODO: explain when a recipe must use this atomic step and what result it produces."
metadata:
  ai-evo-kind: step
  ai-evo-version: "1.0"
  ai-evo-recipe-only: true
---

# TODO: step title

## Purpose

TODO

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs: {}
```

## Procedure

1. Execute the resolved recipe step using the supplied handoff.
2. TODO

## Expected output

TODO

## Constraints

- This step may only be invoked by a recipe.
- TODO

## Success criteria

- TODO

## Examples

```text
uses: <namespace>-step-<skill-name>
```
