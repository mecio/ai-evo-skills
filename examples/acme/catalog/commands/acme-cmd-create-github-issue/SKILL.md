---
name: acme-cmd-create-github-issue
description: Crea una issue GitHub esattamente dalla bozza approvata e autorizzata dallo sviluppatore.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Creazione di una issue GitHub

## Purpose

Crea una issue GitHub esattamente dalla bozza approvata e autorizzata dallo sviluppatore.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [github.remote-write]
inputs:
  issue_draft:
    description: JSON prodotto da acme-cmd-design-github-issue con creation_authorized true.
    required: true
```

## Procedure

1. Valida `issue_draft` rispetto allo schema della progettazione. Richiedi `creation_authorized: true`; non
   completare campi assenti e non cambiare titolo o corpo.
2. Dalla root del repository esegui una sola volta `gh issue create`, passando letteralmente il titolo e il corpo
   approvati mediante argomenti dati, senza editor, prompt, template, assegnatari, label o altri metadati.
3. Conserva l’URL restituito da GitHub e ricavane il numero. Se la chiamata fallisce, riporta diagnostica e URL
   eventualmente restituito; non ripetere automaticamente la creazione.
4. Restituisci esclusivamente il JSON conforme allo schema.

## Expected output

JSON con numero e URL della issue creata, conforme allo schema. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

- Crea una sola issue nella repository corrente.
- Non modificare issue esistenti, pull request, branch, file o configurazione Git.
- L’autorizzazione è valida soltanto per titolo e descrizione presenti nella bozza ricevuta.

## Success criteria

È creata una sola issue con titolo e corpo approvati; numero e URL derivano dalla risposta GitHub.

## Examples

```text
$acme-cmd-create-github-issue
```
