---
name: demo-reviewed-change
description: Runs a review and verifies its findings in a sequential personal workflow.
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Review and verify a change

## Purpose

Compose review and verification into one result.

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills recipe plan demo-reviewed-change` with the current adapter and received inputs.
2. Execute returned command files in order. Replace every `ai-evo-step-output` reference with the complete output
   produced by the referenced earlier step before running the consuming command, and stop at the first failure.
3. Return the declared result.

## Expected output

A verified Markdown review.

## Constraints

- Execute steps sequentially.

## Success criteria

- The verification step receives the review step output.

## Examples

```text
/demo-reviewed-change target=HEAD
```
