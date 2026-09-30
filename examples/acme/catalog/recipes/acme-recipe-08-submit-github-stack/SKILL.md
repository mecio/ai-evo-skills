---
name: acme-recipe-08-submit-github-stack
description: Crea o aggiorna in draft le pull request collegate di uno stack pubblicato e ne sincronizza i metadati.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Submit delle pull request di uno stack GitHub

## Purpose

Creare o aggiornare le pull request collegate dopo la pubblicazione e l'agganciamento degli upstream, mantenendole
in draft e aggiornandone titolo e descrizione in base al lavoro effettivamente svolto.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi
consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usarla soltanto dopo la recipe 07 riuscita. L'invocazione esplicita della recipe e `submit_authorized: "true"`
autorizzano la sola creazione o aggiornamento delle pull request dello stack attivo. Lo step esegue
`gh stack submit --auto`: le nuove PR nascono draft senza editor interattivo; le PR già aperte sono convertite in
draft se necessario. Prima di submit, conversione a draft o modifica di una PR, mostra una tabella di riepilogo e
attende una conferma valida per quel solo comando remoto. Per ciascun layer, titolo e descrizione vengono aggiornati
dal diff incrementale e dalle evidenze di verifica, senza cambiare altri metadati GitHub.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-08-submit-github-stack` e gli input
ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire
soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento
restituire l’output invariato.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Non aprire PR ready for review, non aggiungere reviewer o commenti e non eseguire merge, rebase, sync o force
push. Non creare o aggiornare pull request quando manca l'autorizzazione esplicita.

## Success criteria

Ogni branch dello stack ha una pull request collegata in draft, con titolo e descrizione che rappresentano il
relativo lavoro verificato.

## Examples

```text
$acme-recipe-08-submit-github-stack submit_authorized="true"
```
