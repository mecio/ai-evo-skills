---
name: acme-recipe-01-refine-github-issue
description: Migliora con lo sviluppatore una issue GitHub esistente prima dell’analisi tecnica.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Revisione di una issue GitHub

## Purpose

Migliora con lo sviluppatore una issue GitHub esistente prima dell’analisi tecnica.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala opzionalmente dopo la 00 o su una issue esistente. Rivede titolo e descrizione con lo sviluppatore; un aggiornamento remoto richiede autorizzazione esplicita.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-01-refine-github-issue` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-01-refine-github-issue
```
