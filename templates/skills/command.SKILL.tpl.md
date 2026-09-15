---
name: <namespace>-cmd-<skill-name>
description: "TODO: explain when the AI must use this atomic command and what result it produces."
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# TODO: command title

## Purpose

TODO

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs: {}
```

## Procedure

1. When an `ai-evo-execution-handoff` is supplied, execute its resolved task directly and skip steps 2-4.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan <namespace>-cmd-<skill-name>` with the current adapter, the received
   inputs and the optional `--ai-effort-profile`.
3. Stop if planning or validation fails.
4. Apply the returned working directory, execution mode, native CLI arguments, prompt delivery, policy
   instructions and profile instructions. When `prompt_delivery` is `stdin`, send the complete prompt through
   standard input and never append it to the CLI arguments. For delegated execution, pass the complete
   resolved plan JSON to `.ai-evo/bin/ai-evo-skills command execute` on stdin.
5. TODO

## Expected output

TODO

## Constraints

- TODO

## Success criteria

- TODO

## Examples

```text
/<namespace>-cmd-<skill-name>
```
