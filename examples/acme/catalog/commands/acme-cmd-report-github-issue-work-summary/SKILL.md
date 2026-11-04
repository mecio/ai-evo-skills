---
name: acme-cmd-report-github-issue-work-summary
description: Consolida worklog e stato Git locale di una issue in un riepilogo conclusivo verificabile.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Riepilogo del lavoro locale su una issue

## Purpose

Aggregare gli esiti già registrati nell'attempt corrente e verificare se il target del profilo supervisor è stato
raggiunto, senza rivalutare l'implementazione e senza produrre effetti remoti.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-only
  network: disabled
  capabilities: [acme.workflow-summary]
inputs:
  issue: { required: true, description: "Numero della issue da riepilogare." }
  profile: { default: "supervised-local", description: "Profilo supervisor che definisce il target conclusivo." }
```

## Procedure

Dalla root della checkout esegui
`.ai-evo-prj/scripts/acme-supervisor-github-issue-workflow summarize --issue '<issue>' --profile '<profile>'`
e restituisci invariato il JSON prodotto. Il comando legge l'attempt più recente, verifica i digest degli output
usati, aggrega implementazione, review, commit, test, limiti e decisioni aperte e confronta l'ultimo commit con la
HEAD della worktree registrata. Per un profilo remoto verifica anche pubblicazione dello stack e ricevute delle PR,
includendo nel riepilogo soltanto PR confermate come draft e verificate. Segnala separatamente gli effetti remoti.

## Expected output

JSON conforme a [references/output.schema.json](references/output.schema.json), incluso il riepilogo Markdown nel
campo `report`.

## Constraints

Non modifica worklog, codice o Git e non accede alla rete.

## Success criteria

Il risultato distingue `completed-local`, `completed-draft-prs`, requisiti mancanti, decisioni aperte e violazioni
della policy selezionata.

## Examples

```text
$acme-cmd-report-github-issue-work-summary issue="1234" profile="supervised-local"
```
