---
name: acme-cmd-create-github-issue-breakdown
description: Applica la label epic e crea sub-issue GitHub da una scomposizione approvata e autorizzata.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Creazione della scomposizione GitHub

## Purpose

Applica la label epic e crea sub-issue GitHub da una scomposizione approvata e autorizzata.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [github.remote-write]
inputs:
  breakdown: { required: true, description: "Piano di scomposizione approvato." }
```

## Procedure

Con `mode: single` restituisci una mappa senza modificare GitHub. Con `mode: stacked` non eseguire alcuna operazione GitHub e restituisci una mappa con `parent_issue` e `layers`: ogni layer mantiene `id`, `title`, `body`, `dependencies`, l'ordine numerico in `sequence` ed eventuale `existing_branch`. Con `mode: epic` richiedi
`remote_authorized: true`, verifica che la label `epic` esista, applicala alla issue padre con `gh issue edit`,
poi crea una sola sub-issue per item mediante `gh issue create --parent <numero-padre>` usando titolo e corpo
approvati. Crea nell’ordine delle dipendenze, include nel corpo riferimenti alle dipendenze già create e non
ripete automaticamente operazioni remote fallite. Restituisci numero e URL dell’epic e di ogni sub-issue.

## Expected output

Mappa JSON con numero e URL della issue principale e delle sub-issue create. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Con mode single o stacked non modificare GitHub; non ripetere automaticamente scritture fallite.

## Success criteria

Ogni sub-issue creata corrisponde a un item approvato e le dipendenze sono preservate.

## Examples

```text
$acme-cmd-create-github-issue-breakdown
```
