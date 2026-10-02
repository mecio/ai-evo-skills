---
name: acme-recipe-00-design-github-issue
description: Conduce la progettazione dialogica di una issue e la crea su GitHub soltanto dopo approvazione esplicita dello sviluppatore.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Progettazione e creazione di una issue GitHub

## Purpose

Conduce la progettazione dialogica di una issue e la crea su GitHub soltanto dopo approvazione esplicita dello sviluppatore.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala all’inizio del flusso. L’AI discute il problema una domanda alla volta, propone titolo e descrizione, raccoglie l’approvazione del testo e l’autorizzazione esplicita alla creazione remota. La recipe restituisce numero e URL della nuova issue; non analizza il codice, non crea branch e non modifica la worktree. La sua sessione usa `issue-pending` solo fino alla pianificazione della recipe 01 o 02: il resolver verificato la promuove poi nel percorso `issue-<numero>/attempt-01/00-design-attempt-<nn>`.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-00-design-github-issue --adapter <adapter-corrente>` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-00-design-github-issue
```
