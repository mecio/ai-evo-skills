---
name: acme-cmd-cleanup-github-issue-workspace
description: Rimuove esplicitamente una worktree isolata della issue dopo averne verificato lo stato locale.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Pulizia workspace issue

## Purpose

Rimuovere la worktree isolata registrata per un tentativo concluso, conservando branch e worklog.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.issue-workspace-cleanup]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero della issue." }
  worklog_session_name: { required: true, description: "Una sessione canonica del tentativo da pulire." }
```

## Procedure

Dalla checkout coordinatrice eseguire la capability con `issue` e il `worklog_session_name` della recipe 08
completata. L'helper verifica il checkpoint conclusivo, accetta solo il percorso deterministico registrato,
richiede una worktree pulita e la rimuove con `git worktree remove`.

## Expected output

Il manifesto con `status: cleaned` e data UTC di pulizia.

## Constraints

Non eliminare il branch locale, il worklog o riferimenti remoti. Non forzare la rimozione di modifiche locali.

## Success criteria

La worktree è rimossa e il manifesto conserva l'assegnazione storica.

## Examples

```text
$acme-cmd-cleanup-github-issue-workspace issue="12637" worklog_session_name="issue-12637/attempt-01/08-close-attempt-01"
```
