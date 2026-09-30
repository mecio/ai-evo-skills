---
name: acme-cmd-prepare-github-issue-stack
description: Converte un piano tecnico ready in un manifest locale ordinato di layer Git stacked, senza creare branch o modificare codice.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Preparazione dello stack di una issue GitHub

## Purpose

Converte un piano tecnico ready in un manifest locale ordinato di layer Git stacked, senza creare branch o modificare codice.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-only
  network: disabled
  capabilities: [acme.git-stack-plan]
inputs:
  technical_plan: { required: true, description: "Piano tecnico ready con work item ordinati per dipendenze." }
  issue_number: { required: true, description: "Numero della issue GitHub associata allo stack." }
  issue_title: { required: true, description: "Titolo della issue usato per i nomi dei branch." }
  base_branch: { required: true, description: "Branch base dello stack indicato dallo sviluppatore." }
```

## Procedure

Ricevi un piano tecnico `ready`, il numero e il titolo della issue e il branch base. Verifica che i work item siano ordinati per dipendenze e usa `.ai-evo-prj/scripts/acme-git-stack-plan plan` con il contesto della worktree per produrre nomi e parent deterministici. Associa ogni work item a una sola entry con `base_branch`, `parent_branch`, `branch` e `sequence`; non creare branch, commit, push o PR.

Restituisci solo il JSON conforme allo schema. Se il piano non è `ready`, le dipendenze sono cicliche o non puoi associare un layer a ogni work item, fallisci senza inventare coordinate Git.

## Expected output

Manifest JSON ordinato con base_branch, parent_branch, branch e sequence per ogni work item. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Non creare branch, commit, push o PR; non inventare coordinate Git.

## Success criteria

Ogni work item del piano ready ha esattamente un layer con dipendenze coerenti.

## Examples

```text
$acme-cmd-prepare-github-issue-stack
```
