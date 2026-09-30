---
name: acme-cmd-verify-work-item
description: Esegue le verifiche previste per un work item implementato e decide se è pronto per la review, senza creare commit o modifiche remote.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Verifica di un work item

## Purpose

Esegue le verifiche previste per un work item implementato e decide se è pronto per la review, senza creare commit o modifiche remote.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  work_specification: { required: true, description: "Specifica ready del work item con test_plan e criteri." }
  implementation_report: { required: true, description: "Rapporto delle modifiche applicative eseguite." }
  consolidation_report: { required: true, description: "Rapporto dei test di consolidamento eseguiti." }
```

## Procedure

Leggi la specifica, il rapporto di implementazione e quello di consolidamento, quindi esegui tutte e sole le verifiche previste dal suo `test_plan`: usa i comandi acme per test Feature, Unit o legacy quando applicabili, oltre a lint o build richiesti dalle direttive. Confronta gli esiti con i criteri di accettazione e restituisci `ready-for-review`, `correction-required` o `user-decision-required`, con comandi, esiti, criteri coperti e limiti. Non modificare codice, non creare commit e non pubblicare Git.

## Expected output

Report ready-for-review, correction-required oppure user-decision-required con comandi, esiti e criteri coperti.

## Constraints

Non modificare codice, creare commit o pubblicare Git.

## Success criteria

Tutte le verifiche del test_plan sono eseguite e confrontate con i criteri di accettazione.

## Examples

```text
$acme-cmd-verify-work-item
```
