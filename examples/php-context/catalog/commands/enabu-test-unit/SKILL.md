---
name: enabu-test-unit
description: Run the PHP 8.3 Unit suite when selected by the recipe.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Test unit

## Purpose

Run the PHP 8.3 Unit suite when selected by the recipe.

## Interface

```yaml ai-evo-interface
executor: codex
execution-policy:
  workspace: read-write
  network: disabled
inputs: {}
```

## Procedure

1. If a resolved execution handoff is supplied, perform its task directly; do not call the planner.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan enabu-test-unit` with the current adapter and inputs, then apply the returned execution mode, policy and profile.
3. Confirm that Composer defines `test:unit` and that the configured PHP 8.3 test environment is available. Run `composer run-script test:unit` in that environment. Report the command result and fail the step if the process exits nonzero. Do not install dependencies or change configuration.

## Expected output

The Unit test outcome, including the exit status and relevant failures.

## Constraints

- Honor the resolved execution policy and never replan a delegated task.

## Success criteria

- The requested operation completes and its result is reported faithfully.

## Examples

```text
/enabu-test-unit
```
