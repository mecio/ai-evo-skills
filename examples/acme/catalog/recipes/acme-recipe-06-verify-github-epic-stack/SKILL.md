---
name: acme-recipe-06-verify-github-epic-stack
description: Direct GitHub workflow phase 06-verify-github-epic-stack.
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# GitHub workflow phase 06-verify-github-epic-stack

## Purpose

Execute this bounded workflow phase and preserve its reviewable output.

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

1. Plan the recipe with its received inputs and the invoking adapter.
2. Advance each step in order, preserving its complete output.
3. Stop on failure; after success, let the developer explicitly choose the next phase.

## Expected output

The saved result of this workflow phase.

## Constraints

- The invoking AI coordinates the recipe.
- Do not automatically start a later phase.

## Success criteria

The phase creates one reviewable saved artifact.

## Examples

```text
$acme-recipe-06-verify-github-epic-stack context="<approved context>"
```
