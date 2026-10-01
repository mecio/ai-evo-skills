---
name: acme-recipe-resume-github-issue-workflow
description: Recupera il branch pubblicato di una issue e ricalcola il prossimo passo del workflow.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Ripresa di un workflow GitHub

## Purpose

Riprendere una issue da un checkpoint pubblicato senza richiedere allo sviluppatore di eseguire separatamente il
comando tecnico di recupero del branch.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Il solo input è `issue`.

## Procedure

Avviare questa recipe quando il report restituisce `branch-recovery-required`. Esegue
`acme-cmd-prepare-git-recipe-branch`, quindi rilancia `acme-cmd-report-github-issue-workflow` e restituisce il
suo JSON invariato. Se il trunk è avanzato, il recupero effettua comunque il checkout e il report restituisce
`stack-rebase-required`; dopo rebase e push manuali il report restituisce `stack-republish-required`, da chiudere
richiede `publication_authorized: true`; la stessa recipe registra internamente la ripubblicazione prima di
rilanciare il report.

La recipe è un raccordo, non una fase sequenziale: non crea sessioni o checkpoint nel worklog e non esegue rebase,
merge, `gh stack sync`, push o modifiche GitHub.

## Expected output

Il JSON del report successivo, con la recipe pronta, `stack-rebase-required` oppure una diagnosi bloccante.

## Constraints

Non crea sessioni o checkpoint nel worklog e non esegue rebase, merge, `gh stack sync`, push o modifiche GitHub.

## Success criteria

Il branch pubblicato è disponibile localmente e l'output indica in modo univoco la recipe successiva, il rebase
necessario o la condizione bloccante.

## Examples

```text
$acme-recipe-resume-github-issue-workflow issue="12603"
```
