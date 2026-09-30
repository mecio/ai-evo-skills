---
name: acme-cmd-github-workflow-phase
description: Execute one approved phase of a generic GitHub delivery workflow.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Execute a GitHub workflow phase

## Purpose

Execute one approved GitHub workflow phase and return its complete result.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  context:
    description: Complete approved phase context.
    required: true
  correction_instructions:
    description: Optional explicit corrections to apply within this phase.
    default: ""
```

## Procedure

1. Use the resolved handoff or plan this command with the invoking adapter.
2. Apply the approved context, project rules and any explicit correction instructions.
3. Obtain explicit authorization before a remote write.
4. Return a complete, evidence-backed phase result.

## Expected output

A result ready for persistence and the next workflow phase.

## Constraints

- Do not encode or select an AI executor.

## Success criteria

The operation stays within its approved scope.

## Examples

```text
$acme-cmd-github-workflow-phase context="<approved context>"
```
