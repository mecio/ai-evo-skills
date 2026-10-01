---
name: acme-recipe-02-analyze-github-issue-code
description: Legge una issue GitHub e il codice del progetto per produrre un’analisi tecnica persistente e da approvare.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Analisi tecnica di una issue GitHub

## Purpose

Legge una issue GitHub e il codice del progetto per produrre un’analisi tecnica persistente e da approvare.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per gli attributi e il passaggio tra le fasi consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usala dopo la creazione o l’indicazione di una issue. L’AI legge descrizione, commenti pertinenti, direttive e codice; chiarisce con lo sviluppatore le sole decisioni necessarie, una alla volta. Al termine salva l’analisi pronta in `.ai-evo-work/<sessione>/issue-<numero>-analysis.json`. Non crea work item, branch, commit o modifiche remote. Con `issue="pending"` e `issue_number` il resolver promuove prima la sessione 00 verificata dal percorso pending a quello dell'issue reale, quindi crea questa sessione nello stesso attempt.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-02-analyze-github-issue-code` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`: avanzare con `recipe advance`, eseguire soltanto lo step risolto e conservare integralmente ogni risultato. Fermarsi al primo errore; al completamento restituire l’output invariato.

Se `worklog_session_name` o `worklog_session_input` non sono ricevuti, risolverli prima del piano secondo la convenzione nella [guida alle recipe](../../../acme-recipes.md); non richiederli allo sviluppatore quando sono deducibili dal contesto della fase.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nel worklog della sessione.

## Constraints

Rispettare input, ordine e policy degli step dichiarati. Non avviare automaticamente la fase successiva e non ripetere scritture remote fallite.

## Success criteria

Gli step previsti terminano senza errori e il checkpoint finale conserva il risultato nella sessione richiesta.

## Examples

```text
$acme-recipe-02-analyze-github-issue-code
```
