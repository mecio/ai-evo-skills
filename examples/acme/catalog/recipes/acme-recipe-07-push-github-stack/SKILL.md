---
name: acme-recipe-07-push-github-stack
description: Ripubblica uno stack locale verificato e ne riconferma gli upstream dopo la verifica dei ref remoti.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Pubblicazione di uno stack GitHub

## Purpose

Ripubblicare una catena di branch già verificata e associare ogni branch locale al ref remoto omonimo con lo stesso
OID, senza creare o aggiornare pull request.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi
consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usarla soltanto dopo la recipe 05 per una issue singola o per l'ultimo layer stacked, oppure dopo la recipe 06
per un'epic. La recipe 04 ha già salvato ciascun branch subito dopo il suo primo commit; l'invocazione esplicita
della recipe 07 e `publication_authorized: "true"` autorizzano l'eventuale ripubblicazione finale dello stack
verificato. Prima del push la recipe mostra la tabella di riepilogo richiesta dalle direttive e attende la conferma
per quel comando. Poi verifica ref e OID remoti e riconferma gli upstream locali omonimi. Se il push o la verifica
falliscono, conserva l'evidenza e non ritenta né crea pull request.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-07-push-github-stack --adapter <adapter-corrente>` e gli input
ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire
soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento
restituire l’output invariato.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Non eseguire `gh stack submit`, `gh pr`, force push, sync, rebase, merge o altre operazioni remote oltre al push
autorizzato. Non pubblicare quando manca l'autorizzazione esplicita.

## Success criteria

Lo stack verificato è allineato al remote e ogni upstream locale configurato punta al ref remoto omonimo con OID verificato.

## Examples

```text
$acme-recipe-07-push-github-stack publication_authorized="true"
```
