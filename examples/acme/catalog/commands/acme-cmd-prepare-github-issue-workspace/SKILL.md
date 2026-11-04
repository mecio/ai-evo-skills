---
name: acme-cmd-prepare-github-issue-workspace
description: Prepara e registra la checkout corrente o una worktree isolata per un tentativo di workflow issue.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Preparazione workspace issue

## Purpose

Assegnare una directory operativa persistente all'intero tentativo della issue prima dell'implementazione.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.issue-workspace-prepare]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero della issue." }
  base_branch: { required: true, description: "Trunk locale dal quale parte il lavoro." }
  workspace_mode: { required: true, description: "current oppure isolated." }
  worklog_session_name: { required: true, description: "Sessione canonica che identifica il tentativo." }
```

## Procedure

Dalla root della checkout coordinatrice eseguire la capability `acme.issue-workspace-prepare` con un solo JSON
contenente `issue`, `base_branch`, `workspace_mode` e `worklog_session_name`. Restituire invariato il JSON.

Con `current` la directory assegnata è la checkout corrente. Con `isolated` l'helper crea, o recupera in modo
idempotente, `.sub-worktrees/issues/issue-<n>/attempt-<nn>` detached dall'OID locale del trunk. Collega soltanto
le risorse AI Evo disponibili nel coordinator (`.ai-evo`, progetto, worklog e directory skill); dipendenze,
runtime e tooling applicativi restano responsabilità di capability specifiche del progetto.

## Expected output

Un'assegnazione conforme allo schema, inclusa la `working_directory` assoluta da usare negli step successivi.

## Constraints

Non crea il branch funzionale, non esegue commit e non scrive sul remote.

## Success criteria

La directory assegnata è una root Git valida e contiene soltanto collegamenti gestiti verso risorse AI Evo.

## Examples

```text
$acme-cmd-prepare-github-issue-workspace issue="12637" base_branch="master" workspace_mode="isolated" worklog_session_name="issue-12637/attempt-01/04-implement-attempt-01"
```
