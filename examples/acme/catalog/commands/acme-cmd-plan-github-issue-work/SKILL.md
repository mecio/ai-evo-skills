---
name: acme-cmd-plan-github-issue-work
description: Trasforma un’analisi tecnica approvata di issue GitHub in work item piccoli e verificabili, senza modificare codice o Git.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Piano tecnico di una issue GitHub

## Purpose

Trasforma un’analisi tecnica approvata di issue GitHub in work item piccoli e verificabili, senza modificare codice o Git.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-only
  network: auto
inputs:
  issue_analysis: { required: true, description: "Analisi tecnica approvata della issue." }
  base_branch: { required: true, description: "Branch base dello stack indicato dallo sviluppatore." }
  developer_instructions: { default: "", description: "Vincoli o chiarimenti aggiuntivi dello sviluppatore." }
```

## Procedure

Ricevi un’analisi tecnica già approvata e il branch base. Leggi soltanto il codice necessario e restituisci un piano JSON conforme a `references/output.schema.json`.

Ogni work item deve avere una sola responsabilità, confini chiari, dipendenze esplicite e una strategia di test. Se il piano richiede più di cinque item, una scelta di prodotto o un perimetro non delimitabile, restituisci `user-decision-required` invece di creare uno stack artificiale. Non creare branch, file, commit o modifiche remote.

## Expected output

Piano JSON ready con uno-cinque work item oppure user-decision-required con domande bloccanti. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Non creare branch, file, commit o modifiche remote.

## Success criteria

Ogni item ha responsabilità, dipendenze, criteri e test espliciti; le scelte aperte impediscono lo stato ready.

## Examples

```text
$acme-cmd-plan-github-issue-work
```
