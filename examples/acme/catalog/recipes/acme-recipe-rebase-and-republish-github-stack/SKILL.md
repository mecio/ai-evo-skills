---
name: acme-recipe-rebase-and-republish-github-stack
description: Simula oppure completa rebase, push atomico e registrazione 04r quando il trunk o un layer parent è avanzato.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Rebase e ripubblicazione di uno stack GitHub

## Purpose

Gestire il raccordo 04r causato dall'avanzamento del trunk remoto o dalla correzione di un layer intermedio,
mantenendo nello stesso flusso la simulazione, il push esplicitamente autorizzato e la registrazione dei nuovi OID.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). `publication_authorized` è obbligatorio: false
richiede la sola simulazione, mentre solo true autorizza il push atomico e la successiva registrazione 04r.

## Procedure

Usare la recipe per lo stato `stack-rebase-required`. Quando il report indica `parent_branch`, il comando ribasa
e ripubblica soltanto il figlio indicato e i suoi discendenti.

Con `publication_authorized=false`, restituisce `stack-rebase-simulated` senza modificare branch, worktree o ref
remoti. Con `publication_authorized=true`, esegue rebase e push atomico verificati, allinea trunk e layer locali,
registra la ripubblicazione tramite il comando 04r esistente e restituisce il report successivo.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-rebase-and-republish-github-stack --adapter <adapter-corrente>`
e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`,
eseguire soltanto lo step risolto e conservare integralmente il risultato.

## Expected output

Il valore `outputs.result`: simulazione, conflitto, blocco oppure report aggiornato dopo la registrazione 04r.

## Constraints

Non dedurre l'autorizzazione da richieste precedenti. Non eseguire il push se `publication_authorized` non è
letteralmente true. Non creare o modificare pull request e non eseguire
submit, sync o merge remoto.

## Success criteria

La simulazione lascia invariati i ref; l'esecuzione autorizzata termina con stack remoto e locale allineati,
checkpoint 04r registrati e un report che indica il prossimo passo del workflow.

## Examples

```text
$acme-recipe-rebase-and-republish-github-stack issue="12724" publication_authorized="false"
$acme-recipe-rebase-and-republish-github-stack issue="12724" publication_authorized="true"
```
