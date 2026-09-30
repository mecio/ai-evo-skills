---
name: acme-cmd-implement-github-issue
description: Implementa una issue esecutiva in un branch Git stacked, con pre-test, codice, consolidamento e commit logici.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Implementazione di una issue GitHub

## Purpose

Implementa una issue esecutiva in un branch Git stacked, con pre-test, codice, consolidamento e commit logici.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.git-prepare-branch, acme.git-commit, github.auth-status, github.repo-view, github.issue-view]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero o URL della issue principale o sub-issue esecutiva." }
  base_branch: { required: true, description: "Branch base o parent dello stack indicato dallo sviluppatore." }
  layer: { default: "", description: "JSON opzionale con id, sequence, title, body e dependencies del layer stacked." }
  previous_review: { default: "", description: "Percorso opzionale della review verificata del layer precedente." }
  developer_instructions: { default: "", description: "Vincoli operativi ulteriori." }
```

## Procedure

Leggi con `gh` la issue indicata e usa esclusivamente il lavoro, i pre-test, la modifica e i test di consolidamento già descritti e approvati. Il `base_branch` fornito dal resolver prevale su ogni proposta nella issue. Se `previous_review` è valorizzato, leggila soltanto come contesto: non chiudere automaticamente i findings; chiudi solo quelli richiamati in `developer_instructions` o nel body del layer e riporta in `open_decisions` quelli verificati che restano aperti. Se `layer` è valorizzato, valida il JSON, implementa esclusivamente `body` di quel layer e crea con `gh stack add` il branch il cui suffisso è generato da `acme-git-stacked-branch-name --sequence <sequence> --item <title>`; `L0` parte dal trunk e ogni layer successivo dal `base_branch` risolto. Altrimenti conserva il flusso esistente con `gh stack init` o `gh stack add`. Da worktree pulita attua nell’ordine pre-test, modifica del codice e test di consolidamento. Nei test che attraversano driver, identifier o model, usare JsonDb con fixture JSON quando la query reale è supportata, evitando stub o mock di tali componenti; per una query non emulabile, riportare il limite e isolare soltanto quel confine. Crea tutti e soli i commit logici necessari, ciascuno con soggetto che inizia `#<issue> `. Esegui le suite previste, conserva evidenze e restituisci branch, parent, commit ordinati, test e limiti; per un layer restituisci anche `layer_id`. Se la issue è ambigua o richiede lavoro non descritto, fermati e chiedi allo sviluppatore una domanda alla volta. Non eseguire push, submit o altre operazioni remote di scrittura: la recipe 04 affida il push iniziale al comando successivo, separato e verificabile.

## Expected output

Un JSON conforme a [references/output.schema.json](references/output.schema.json), con coordinate del branch,
commit, test, decisioni aperte, limiti e il report Markdown nel campo `report`. Quando `layer` è valorizzato,
includere anche il relativo `layer_id`.

## Constraints

Restare nel lavoro approvato; non eseguire push, submit o scritture remote.

## Success criteria

Pre-test, modifica e consolidamento sono completati con evidenze e commit riferiti alla stessa issue.

## Examples

```text
$acme-cmd-implement-github-issue
```
