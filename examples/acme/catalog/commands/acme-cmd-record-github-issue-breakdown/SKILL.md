---
name: acme-cmd-record-github-issue-breakdown
description: Registra la mappa approvata o creata delle sub-issue nel worklog della issue principale.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Registrazione della scomposizione

## Purpose

Registra la mappa approvata o creata delle sub-issue o dei layer nel worklog della issue principale.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.issue-breakdown-record]
inputs:
  session_name: { required: true, description: "Percorso relativo della sessione .ai-evo-work." }
  breakdown: { required: true, description: "Mappa prodotta da acme-cmd-create-github-issue-breakdown." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-record-github-issue-breakdown record` con sessione e JSON della scomposizione creata. Restituisci il JSON invariato. Il file è `.ai-evo-work/<sessione>/issue-<numero>-breakdown.json`.

## Expected output

JSON invariato e file issue-<numero>-breakdown.json nella sessione. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Limitare la scrittura al worklog della sessione; non modificare GitHub.

## Success criteria

La mappa della scomposizione è persistita senza alterazioni.

## Examples

```text
$acme-cmd-record-github-issue-breakdown
```
