---
name: acme-cmd-design-work-test-coverage
description: Progetta la copertura di test mancante per un singolo work item, senza modificare file.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Progettazione della copertura di test

## Purpose

Progetta la copertura di test mancante per un singolo work item, senza modificare file.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-only
  network: auto
inputs:
  work_specification: { required: true, description: "Work item ready della sub-issue." }
```

## Procedure

Leggi work item, direttive di qualità, test esistenti e codice interessato. Individua il comportamento non coperto e progetta solo i test necessari prima della modifica: suite, file, fixture, baseline, casi positivi, negativi e regressioni. Per ogni caso che attraversa driver, identifier o model, verifica se la query reale è supportata da JsonDb e, se lo è, pianifica fixture JSON e componenti reali invece di stub o mock; se non lo è, indica il limite e il solo confine da isolare. Se la copertura esistente è sufficiente, dichiaralo con evidenze. Restituisci un piano di copertura pronto da attuare; non modificare codice, test, Git o servizi remoti.

## Expected output

Piano con suite, file, fixture, baseline e casi di test necessari, oppure evidenze della copertura già sufficiente.

## Constraints

Non modificare codice, test, Git o servizi remoti.

## Success criteria

Il piano collega i test mancanti ai comportamenti del work item senza duplicare la copertura esistente.

## Examples

```text
$acme-cmd-design-work-test-coverage
```
