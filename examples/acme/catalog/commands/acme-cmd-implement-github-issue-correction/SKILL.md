---
name: acme-cmd-implement-github-issue-correction
description: Applica correzioni esplicite a un'implementazione GitHub locale già committata e non pubblicata.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Correzione di un'implementazione di issue GitHub

## Purpose

Applica solo le correzioni richieste dallo sviluppatore a un branch già implementato, senza riprendere la sessione nativa dell'executor e senza riscrivere i commit esistenti.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.git-commit, github.auth-status, github.repo-view, github.issue-view]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero o URL della issue esecutiva." }
  branch: { required: true, description: "Branch locale già implementato e non pubblicato." }
  parent_branch: { required: true, description: "Parent immutabile del branch registrato dalla recipe 04." }
  layer: { default: "", description: "JSON opzionale del layer stacked." }
  correction_instructions: { required: true, description: "Correzioni esplicite dello sviluppatore; non può essere vuoto." }
  implementation_report: { required: true, description: "Output registrato del checkpoint implement_issue della recipe 04." }
  developer_instructions: { default: "", description: "Vincoli originali dell'implementazione." }
```

## Procedure

Verifica che la worktree sia pulita e che il branch corrente coincida esattamente con `branch`. Verifica che `implementation_report` descriva lo stesso `branch` e `parent_branch`, quindi elenca tutti i commit in `parent_branch..branch`. Non eseguire `gh stack init`, `gh stack add`, rebase, amend né altra riscrittura dei commit esistenti. Applica soltanto `correction_instructions`; se riguardano test di caratterizzazione, esegui prima il pre-test oppure riverifica il comportamento del codice originale. Nei test che attraversano driver, identifier o model, usa JsonDb con fixture JSON quando la query reale è supportata; per una query non emulabile, dichiara il limite e isola soltanto quel confine. Crea soltanto commit logici aggiuntivi, ciascuno con soggetto `#<issue> `. Esegui le suite pertinenti. Non eseguire push, submit o scritture remote.

## Expected output

Restituisci il JSON dello schema di implementazione riportato in `references/output.schema.json`: `commits` contiene l'elenco completo e ordinato dei commit in `parent_branch..branch`, inclusi quelli originali e di correzione. Aggiorna `tests`, `open_decisions` e `limits`; nel campo `report` distingui chiaramente correzioni richieste, verifiche/pre-test, commit aggiunti e limiti residui. Se `layer` è valorizzato, restituisci anche `layer_id`.

## Constraints

La sessione è autonoma rispetto alla recipe 04 e non esegue scritture remote.

## Success criteria

La worktree resta sul branch registrato, i commit originali restano invariati, le sole correzioni richieste sono
committate e le suite pertinenti hanno evidenza nel report.

## Examples

```text
$acme-cmd-implement-github-issue-correction issue="12589" branch="feature/..." parent_branch="master" correction_instructions="Usare JsonDb."
```
