---
name: demo-verify
description: Verifies an earlier review against the current code and returns confirmed findings.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Verify a review

## Purpose

Check every proposed finding against the reviewed Git target.

## Interface

```yaml ai-evo-interface
executor: current
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  review:
    description: Review produced by the previous step.
    required: true
  target:
    description: Git branch, commit or diff being reviewed.
    required: true
```

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills command plan demo-verify` with the current adapter and received inputs.
2. Apply the returned working directory, execution mode, native CLI arguments, policy instructions and profile
   instructions.
3. Retain only findings supported by current code.

## Expected output

A final Markdown review containing confirmed findings.

## Constraints

- Do not modify the worktree.

## Success criteria

- Every retained finding has been checked against the target.

## Examples

```text
/demo-verify review="<previous output>" target=HEAD
```
