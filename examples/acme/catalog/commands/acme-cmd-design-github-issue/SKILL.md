---
name: acme-cmd-design-github-issue
description: Conduce una discussione una domanda alla volta e produce una bozza di issue GitHub approvata e autorizzata alla pubblicazione.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Progettazione dialogica di una issue GitHub

## Purpose

Conduce una discussione una domanda alla volta e produce una bozza di issue GitHub approvata e autorizzata alla pubblicazione.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  problem_description:
    description: Descrizione iniziale libera del problema fornita dallo sviluppatore.
    required: true
```

## Procedure

1. Parti dalla descrizione iniziale e chiedi una sola domanda alla volta. Dopo ogni risposta, sintetizza ciò che
   hai capito solo quando serve a chiarire il punto successivo.
2. Esplora obiettivo, persone o sistemi coinvolti, comportamento attuale e atteso, confini, casi esclusi,
   vincoli, dipendenze, rischi e criteri di accettazione. Non analizzare codice e non trasformare ipotesi in
   requisiti senza discuterle.
3. Quando il perimetro è sufficiente, proponi un titolo conciso e una descrizione completa della issue con
   contesto, obiettivo, requisiti, criteri di accettazione, vincoli, non-obiettivi e decisioni prese.
4. Chiedi se il testo piace. Applica eventuali correzioni e ripeti questa domanda finché lo sviluppatore non
   approva esplicitamente titolo e descrizione.
5. Mostra il testo approvato e chiedi separatamente l’autorizzazione esplicita a creare l’issue su GitHub.
   Senza una risposta affermativa non terminare con un output pubblicabile e non eseguire chiamate remote.
6. Restituisci esclusivamente il JSON conforme allo schema, includendo letteralmente titolo e descrizione
   approvati e `creation_authorized: true`.

## Expected output

Bozza JSON con titolo e descrizione approvati e creation_authorized true. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

- Non porre elenchi di domande né saltare la discussione dei confini.
- Non creare issue, commenti, branch, commit o file.
- Non usare informazioni della conversazione non confermate dallo sviluppatore come requisiti.

## Success criteria

Titolo e descrizione sono approvati e la creazione remota è autorizzata esplicitamente.

## Examples

```text
$acme-cmd-design-github-issue
```
