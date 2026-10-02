---
name: acme-recipe-06-verify-github-epic-stack
description: Verifica uno stack di sub-issue completate rispetto alla relativa epic.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Verifica dello stack di una epic

## Purpose

Verifica uno stack di sub-issue completate rispetto alla relativa epic.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala soltanto quando la recipe 03 ha creato un’epic con sub-issue. Confronta analisi della principale, mappa delle sub-issue ed evidenze dei layer; un’issue non scomposta termina invece con la recipe 05.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-06-verify-github-epic-stack --adapter <adapter-corrente>` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-06-verify-github-epic-stack
```
