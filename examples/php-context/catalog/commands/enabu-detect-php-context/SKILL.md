---
name: enabu-detect-php-context
description: Detect the project PHP context from its Composer platform declaration.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Detect php context

## Purpose

Detect the project PHP context from its Composer platform declaration.

## Interface

```yaml ai-evo-interface
executor: current
execution-policy:
  workspace: read-only
  network: disabled
inputs: {}
```

## Procedure

1. If a resolved execution handoff is supplied, perform its task directly; do not call the planner.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan enabu-detect-php-context` with the current adapter and inputs, then apply the returned execution mode, policy and profile.
3. Read `composer.json` and its `config.platform.php` declaration. Return `php72` for a 7.2 version or `php83` for an 8.3 version. Return only that token, without explanations or Markdown. The recipe's explicit `normalize: trim` tolerates a trailing newline added by the native client. If the declaration is absent or unsupported, report failure instead of guessing.

## Expected output

The token `php72` or `php83`; the native client may append a newline.

## Constraints

- Honor the resolved execution policy and never replan a delegated task.

## Success criteria

- The requested operation completes and its result is reported faithfully.

## Examples

```text
/enabu-detect-php-context
```
