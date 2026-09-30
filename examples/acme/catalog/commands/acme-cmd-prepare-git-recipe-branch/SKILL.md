---
name: acme-cmd-prepare-git-recipe-branch
description: Recupera e aggiorna in sicurezza il branch remoto già registrato da una recipe, anche se è uno stack.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Preparazione del branch di una recipe

## Purpose

Riallineare una worktree al branch già registrato da una recipe prima di riprenderne gli step su un'altra
postazione.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.git-prepare-recipe-branch]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  branch: { required: true, description: "Nome letterale del branch già registrato dalla recipe." }
  branch_type: { required: true, description: "`standard` per un branch Git ordinario, `stacked` per un layer gh stack." }
```

## Procedure

1. Ricavare `branch` e `branch_type` dal checkpoint o dagli input immutabili della recipe; non dedurre il branch
   dal branch corrente. Il tipo `stacked` è obbligatorio per un layer di uno stack.
2. Dalla root applicativa eseguire `.ai-evo-prj/scripts/acme-git-recipe-branch prepare '<JSON>'`, passando un unico JSON
   con `branch` e `branch_type` come dato quotato. L'helper richiede una worktree pulita, legge `stack_remote`
   dalla configurazione, aggiorna i ref remoti e verifica il ref atteso.
3. Per `standard`, l'helper seleziona il branch locale oppure crea la tracking checkout dal ref remoto. Per
   `stacked`, esegue `gh stack checkout <branch>` per recuperare o selezionare l'intero stack. In entrambi i casi
   verifica l'upstream omonimo sul remote configurato ed esegue soltanto `git pull --ff-only`.
4. Restituire il JSON invariato dell'helper. Al primo errore conservare la diagnostica e non eseguire checkout
   alternativi, merge, rebase, `gh stack sync`, push o modifiche del worklog.

## Expected output

Un JSON conforme a [references/output.schema.json](references/output.schema.json), con branch, tipo, remote,
upstream, azione eseguita e OID aggiornato.

## Constraints

- Il branch deve essere già registrato dalla recipe e presente sul remote configurato.
- Richiede worktree pulita e non crea commit, branch alternativi, pull request o scritture remote.
- `gh stack sync` è vietato: può eseguire rebase e push dello stack.

## Success criteria

`HEAD` coincide con il branch registrato, che traccia il ref omonimo del remote e risulta aggiornato con un
fast-forward sicuro.

## Examples

```text
$acme-cmd-prepare-git-recipe-branch branch="feature/0.0_#123_example" branch_type="standard"
$acme-cmd-prepare-git-recipe-branch branch="feature/0.0_#123_example/01_work_item" branch_type="stacked"
```
