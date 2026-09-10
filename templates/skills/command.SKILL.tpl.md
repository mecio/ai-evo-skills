---
name: <namespace>-<skill-name>
description: TODO: explain when the AI must use this atomic command and what result it produces.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# TODO: command title

## Purpose

TODO

## Interface

```yaml ai-evo-interface
executor: current
execution-policy:
  workspace: read-write
  network: auto
inputs: {}
```

## Procedure

1. Run `.ai-evo/bin/ai-evo-skills command plan <namespace>-<skill-name>` with the current adapter, the received
   inputs and the optional `--ai-effort-profile`.
2. Stop if planning or validation fails.
3. Apply the returned working directory, execution mode, native CLI arguments, policy instructions and profile
   instructions.
4. TODO

## Expected output

TODO

## Constraints

- TODO

## Success criteria

- TODO

## Examples

```text
/<namespace>-<skill-name>
```
