---
name: acme-cmd-consolidate-work-tests
description: Completa e esegue i test della soluzione implementata per un singolo work item, senza creare commit.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Consolidamento dei test di un work item

## Purpose

Completa e esegue i test della soluzione implementata per un singolo work item, senza creare commit.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  work_specification: { required: true, description: "Work item ready della sub-issue." }
  coverage_report: { required: true, description: "Rapporto della copertura preventiva." }
  implementation_report: { required: true, description: "Rapporto della modifica applicativa." }
```

## Procedure

Ricevi la specifica, il rapporto di copertura preventiva e quello di implementazione. Aggiorna o aggiungi soltanto test, fixture e supporti necessari a dimostrare i criteri di accettazione e le regressioni corrette. Per percorsi con driver, identifier o model, mantenere o introdurre JsonDb con fixture JSON quando la query è supportata, così da coprire il flusso reale; usare stub o mock solo per un limite SQL o di confine documentato. Esegui le suite previste dalle direttive e dal work item, includendo i test preventivi. Riporta file, comandi, esiti, criteri coperti e limiti; non modificare codice applicativo, non creare commit e non pubblicare Git.

## Expected output

Rapporto con file di test, comandi eseguiti, esiti, criteri coperti e limiti.

## Constraints

Modificare soltanto test, fixture e supporti; non creare commit.

## Success criteria

I test preventivi e di consolidamento sono eseguiti e gli eventuali fallimenti sono documentati.

## Examples

```text
$acme-cmd-consolidate-work-tests
```
