---
name: acme-recipe-05-review-github-issue
description: Revisiona l’implementazione di una issue rispetto al parent del suo branch stacked.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Review di una issue GitHub

## Purpose

Revisiona l’implementazione di una issue rispetto al parent del suo branch stacked.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala dopo la recipe 04. Prima di pianificarla o recuperarla, invoca `acme-cmd-prepare-git-recipe-branch issue="<issue>"` con la issue della recipe: legge il branch pubblicato dal worklog, ripristina o ricostruisce lo stack e fa un solo pull fast-forward, anche quando la recipe viene avviata da un'altra postazione. Revisiona tutti i commit logici dell’issue nel branch corrente; se `base` non è fornita, i comandi risolvono il parent stacked. Per un layer `stacked`, `work_specification` contiene il JSON del layer e vincola review e verifica a obiettivo, perimetro e criteri. La review verificata viene salvata sia nel checkpoint non conclusivo sia in `issue-<numero>-review.md`; una review con correzioni resta evidenza per lo sviluppatore e per il layer successivo. La verifica finale controlla base, parent, branch, sequenza, commit logici e worktree del layer.

Se il trunk è avanzato, `verify_layer` non produce `verified`: completare rebase, push e registrazione della
ripubblicazione tramite la recipe di ripresa prima di rieseguire la review.

Un checkpoint `verify_review` non conclusivo resta immutabile; al rilancio il report apre
`05-review-attempt-02` e collega la review precedente come evidenza, senza sovrascrivere l'artefatto della prima
sessione.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-05-review-github-issue --adapter <adapter-corrente>` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-05-review-github-issue
```
