---
name: acme-recipe-04-implement-github-issue
description: Implementa una issue esecutiva su un branch stacked con test e commit logici.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Implementazione di una issue GitHub

## Purpose

Implementa una issue esecutiva su un branch stacked con test e commit logici.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala per una issue principale non scomposta, una sub-issue o un layer `stacked`. Con `layer` vuoto il comportamento è invariato. Con il JSON del layer implementa soltanto il suo perimetro: usa il branch del layer precedente come `base_branch` (il trunk risolto per il contesto della worktree da `acme-worktree-context` per `L0`), crea il branch con `gh stack add` e un suffisso ottenuto da `acme-git-stacked-branch-name`, e restituisce anche `layer_id` e `branch`. Dopo pre-test, codice, consolidamento e almeno un commit logico, la recipe pubblica subito il solo branch sul `stack_remote` configurato, ne verifica l'OID e imposta l'upstream: questo checkpoint rende il layer recuperabile da un'altra worktree prima della review. Non crea o aggiorna pull request. Quando i test attraversano driver, identifier o model, lo step di implementazione applica la direttiva JsonDb: usa fixture JSON e componenti reali per query supportate e documenta il solo confine da isolare se non lo sono.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-04-implement-github-issue` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite. Il push iniziale del branch è parte obbligatoria della recipe 04; la recipe 07 resta la pubblicazione finale esplicitamente autorizzata dell'intero stack verificato.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-04-implement-github-issue
```
