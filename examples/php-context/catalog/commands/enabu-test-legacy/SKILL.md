---
name: enabu-test-legacy
description: Run the project legacy tests under its configured PHP environment.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Test legacy

## Purpose

Run the project legacy tests under its configured PHP environment.

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
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan enabu-test-legacy` with the current adapter and inputs, then apply the returned execution mode, policy and profile.
3. Confirm that Composer defines `test:legacy` and that the project test environment is available. Run `composer run-script test:legacy` using the project environment documented by the team. Report the command result and fail the step if the process exits nonzero. Do not install dependencies or change configuration.

## Expected output

The legacy test outcome, including the exit status and relevant failures.

## Constraints

- Honor the resolved execution policy and never replan a delegated task.

## Success criteria

- The requested operation completes and its result is reported faithfully.

## Examples

```text
/enabu-test-legacy
```
