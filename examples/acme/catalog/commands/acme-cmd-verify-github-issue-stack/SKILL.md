---
name: acme-cmd-verify-github-issue-stack
description: Verifica in sola lettura uno stack locale rispetto a specifica, piano tecnico ed evidenze disponibili.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Verifica finale di una issue GitHub

## Purpose

Verifica in sola lettura uno stack locale rispetto a specifica, piano tecnico ed evidenze disponibili.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-only
  network: auto
inputs:
  issue_analysis: { required: true, description: "Analisi tecnica approvata della issue." }
  technical_plan: { required: true, description: "Piano tecnico ready con work item ordinati per dipendenze." }
  base_branch: { required: true, description: "Branch base dello stack indicato dallo sviluppatore." }
  verification_evidence: { default: "", description: "Report di test e verifiche già eseguite sui layer." }
```

## Procedure

Confronta specifica, piano tecnico, commit e diff locali dal branch base. Verifica che ogni work item abbia evidenze di test e che nessun requisito sia privo di copertura. Restituisci `accepted`, `correction-required` oppure `user-decision-required`, con evidenze puntuali e limiti residui. Non modifica codice, Git o servizi remoti e non ripete test già documentati se il codice non è cambiato.

Input: `issue_analysis` e `technical_plan` sono richiesti; `base_branch` è richiesto; `verification_evidence` è opzionale.

## Expected output

Report accepted, correction-required oppure user-decision-required con evidenze e limiti.

## Constraints

Non modificare codice, Git o servizi remoti; non ripetere test documentati a codice invariato.

## Success criteria

Il report collega requisiti e work item a commit, diff ed evidenze, segnalando ogni lacuna.

## Examples

```text
$acme-cmd-verify-github-issue-stack
```
