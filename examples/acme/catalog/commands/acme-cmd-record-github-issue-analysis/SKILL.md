---
name: acme-cmd-record-github-issue-analysis
description: Registra un’analisi tecnica pronta nel file di lavoro della sessione .ai-evo-work identificato dal numero issue.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Registrazione dell’analisi tecnica

## Purpose

Registra un’analisi tecnica pronta nel file di lavoro della sessione .ai-evo-work identificato dal numero issue.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.issue-analysis-record]
inputs:
  session_name: { required: true, description: "Percorso relativo della sessione .ai-evo-work." }
  analysis: { required: true, description: "Analisi JSON ready prodotta da acme-cmd-analyze-github-issue-code." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-record-github-issue-analysis record` passando il nome della sessione e l’analisi JSON
ricevuta. Restituisci invariato il JSON prodotto dallo script. Il file prodotto è
`.ai-evo-work/<sessione>/issue-<numero>-analysis.json`; non modificare codice, Git o GitHub.

## Expected output

JSON invariato dello script e file issue-<numero>-analysis.json nella sessione. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Non modificare codice, Git o GitHub.

## Success criteria

Il file della sessione contiene l’analisi ricevuta e l’output dello script è preservato.

## Examples

```text
$acme-cmd-record-github-issue-analysis
```
