---
name: acme-recipe-04-implement-github-issue-correction
description: Corregge con commit aggiuntivi un'implementazione locale non pubblicata o già revisionata e pubblicata.
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Correzione locale dell'implementazione GitHub

## Purpose

Correggere un'implementazione già committata, prima della pubblicazione oppure dopo una review del corrente OID pubblicato, senza riusare la sessione nativa di Claude.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per sessioni e passaggi di fase consultare la
[guida alle recipe](../../../acme-recipes.md).

## Procedure

Il resolver la propone dopo un checkpoint `implement_issue` riuscito senza `publish_branch`, oppure dopo una 05
conclusa sull'OID pubblicato corrente, e solo quando lo sviluppatore fornisce `correction_instructions` non vuote.
Nel secondo caso aggiorna il report di implementazione alla storia corrente e collega la review in `source_review`.
La recipe apre una sessione autonoma, registra un checkpoint non conclusivo, pubblica il branch con un push
fast-forward e conserva il nuovo `remote_oid` nel risultato conclusivo. Non modifica il piano o il journal della sessione 04 originaria.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-04-implement-github-issue-correction --adapter <adapter-corrente>`
e gli input risolti. Seguire il protocollo in `.ai-evo/docs/recipe-runtime.md`: avanzare solo lo step risolto e
fermare la recipe al primo errore. Il push è confinato allo step `publish_branch`.

## Expected output

Il valore `outputs.result` di `recipe.yaml`: il report di implementazione aggiornato, con tutti i commit del branch
rispetto al parent e la distinzione delle correzioni applicate.

## Constraints

Non usare `gh stack init`, `gh stack add`, rebase o amend. Non eseguire scritture remote fuori da `publish_branch`.

## Success criteria

Il checkpoint finale conserva un report conforme al contratto di implementazione, con tutti i commit del branch e le correzioni distinguibili.

## Examples

```text
$acme-recipe-04-implement-github-issue-correction correction_instructions="Correggi il test con JsonDb."
```
