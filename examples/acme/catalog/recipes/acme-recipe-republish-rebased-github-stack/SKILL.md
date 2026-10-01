---
name: acme-recipe-republish-rebased-github-stack
description: Registra i nuovi OID di uno stack già ribasato e pubblicato manualmente.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Ripubblicazione registrata di uno stack ribasato

## Purpose

Chiudere il percorso `stack-rebase-required` aggiornando la fonte di verità del worklog senza riscrivere checkpoint.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml).

## Procedure

Dopo il rebase e il push manuali, avvia questa recipe quando il report restituisce `stack-republish-required`.
Verifica che ogni patch pubblicata prima del rebase corrisponda a quella ribasata e registra i nuovi checkpoint.
Al completamento rilancia `acme-recipe-resume-github-issue-workflow` per calcolare il passo successivo.

## Expected output

Il rapporto dei checkpoint `publish_branch` aggiunti per tutti i layer.

## Constraints

Non effettua rebase, merge o push e non modifica checkpoint esistenti.

## Success criteria

Il report torna `ready` e `acme-cmd-prepare-git-recipe-branch` non rileva più una riscrittura del remote.

## Examples

```text
$acme-recipe-republish-rebased-github-stack issue="12603" publication_authorized="true"
```
