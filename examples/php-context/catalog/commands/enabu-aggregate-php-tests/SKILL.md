---
name: enabu-aggregate-php-tests
description: Summarize legacy and conditional Unit test outcomes without treating skips as passes.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Aggregate php tests

## Purpose

Summarize legacy and conditional Unit test outcomes without treating skips as passes.

## Interface

```yaml ai-evo-interface
executor: current
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  legacy:
    description: Complete legacy test output
    required: true
  unit:
    description: Complete Unit output or JSON text of an ai-evo-step-skipped state
    required: true
```

## Procedure

1. If a resolved execution handoff is supplied, perform its task directly; do not call the planner.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan enabu-aggregate-php-tests` with the current adapter and inputs, then apply the returned execution mode, policy and profile.
3. Read both supplied inputs. If `unit` parses as an object with `type: ai-evo-step-skipped`, `step: unit_tests` and `reason: condition-false`, report Unit tests as skipped for PHP 7.2. Otherwise summarize the Unit output. Always summarize legacy output. Do not execute tests, and never label a skipped suite as passed.

## Expected output

A report that distinguishes executed test results from the intentionally omitted Unit suite.

## Constraints

- Honor the resolved execution policy and never replan a delegated task.

## Success criteria

- The requested operation completes and its result is reported faithfully.

## Examples

```text
/enabu-aggregate-php-tests
```
