---
name: acme-recipe-03-breakdown-github-issue
description: Decide e applica la scomposizione di una issue tecnica in sub-issue GitHub, solo dopo approvazione esplicita.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Scomposizione di una issue GitHub

## Purpose

Decide e applica la scomposizione di una issue tecnica in sub-issue GitHub, solo dopo approvazione esplicita.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala dopo l’analisi tecnica. Se l’issue è unitaria, registra una mappa senza operazioni remote. Se richiede più lavori autonomi, discute e fa approvare la scomposizione, poi applica la label `epic` alla principale e crea sub-issue figlie. Per lavori sequenziali sullo stesso componente può registrare `stacked` senza scritture GitHub. Il risultato persistente contiene gli ID e URL, oppure i layer, che alimentano le fasi successive.

Quando una scomposizione conclusa deve essere sostituita, passa `new_workflow_attempt="true"` e un `reason` non vuoto. Il resolver apre un nuovo attempt della sola fase 03, riusando l'analisi conclusa dell'attempt corrente; non usarlo se l'attempt ha sessioni da recuperare o ha già creato sub-issue remote.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-03-breakdown-github-issue --adapter <adapter-corrente>` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-03-breakdown-github-issue
```
