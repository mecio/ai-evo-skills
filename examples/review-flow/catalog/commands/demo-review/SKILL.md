---
name: demo-review
description: Reviews a requested Git target and returns evidence-based findings.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Review a Git target

## Purpose

Inspect a Git target and identify concrete defects.

## Interface

```yaml ai-evo-interface
executor: current
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  target:
    description: Git branch, commit or diff to review.
    required: true
```

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills command plan demo-review` with the current adapter and received inputs.
2. Apply the returned working directory, execution mode, native CLI arguments, policy instructions and profile
   instructions.
3. Review the target and cite file and line evidence.

## Expected output

A Markdown list of findings ordered by severity.

## Constraints

- Do not modify the worktree.

## Success criteria

- Every finding contains reproducible evidence.

## Examples

```text
/demo-review target=HEAD
```
