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
  issue: { required: true, description: "Numero della issue il cui attempt più recente contiene il checkpoint publish_branch." }
  worklog_session: { default: "", description: "Sessione di worklog da usare al posto dell'attempt più recente." }
  branch: { default: "", description: "Controllo facoltativo: se valorizzato deve coincidere con il branch pubblicato nel worklog." }
```

## Procedure

1. Leggere dal worklog dell'`issue` i checkpoint `publish_branch` riusciti dell'attempt più recente; se presente,
   `worklog_session` limita la lettura a quella sessione. Un `branch` esplicito è solo un controllo e deve
   coincidere con il tipo dello stack registrato.
2. Dalla root applicativa eseguire `.ai-evo-prj/scripts/acme-git-recipe-branch prepare '<JSON>'`, passando un unico JSON
   con `issue`, `worklog_session` e `branch` come dato quotato. L'helper richiede una worktree pulita, legge
   `stack_remote` dalla configurazione, aggiorna i ref remoti e verifica ogni OID pubblicato.
3. Se il trunk è avanzato dopo la pubblicazione del primo layer, il comando accetta esplicitamente la catena,
   restituisce `rebase_required: true` con trunk, OID e base comune, ed esegue comunque il checkout. Non effettua
   alcun rebase automatico. Una catena non lineare resta bloccante solo tra layer oppure con un parent non correlato.
   Se lo stack è già tracciato, esegue `gh stack checkout <branch>`. Altrimenti verifica che ogni ref remoto
   contenga il rispettivo `remote_oid`, ricostruisce la catena trunk→layer dal campo `parent_branch`, crea i soli
   tracking branch mancanti e usa `gh stack init --base <trunk> <layer...>` per adottarli. Se non esiste alcun
   checkpoint pubblicato, usa `gh stack checkout` per il caso di stack già pubblicato tramite PR.
4. Verifica l'upstream omonimo sul remote configurato ed esegue soltanto `git pull --ff-only`. Restituire il JSON
   invariato dell'helper. Al primo errore conservare la diagnostica e non eseguire checkout
   alternativi, merge, rebase, `gh stack sync`, push o modifiche del worklog.

## Expected output

Un JSON conforme a [references/output.schema.json](references/output.schema.json), con branch, remote, upstream,
azione eseguita e OID aggiornato, oltre a `rebase_required`, `trunk`, `trunk_oid` e `layer_base_oid`.

## Constraints

- La fonte di verità è il worklog: non cercare branch per convenzione di nome né dedurli da `HEAD`.
- Richiede worktree pulita e non crea commit, branch alternativi, pull request o scritture remote.
- `gh stack sync` è vietato: può eseguire rebase e push dello stack.

## Success criteria

`HEAD` coincide con il branch registrato, che traccia il ref omonimo del remote e risulta aggiornato con un
fast-forward sicuro.

## Examples

```text
$acme-cmd-prepare-git-recipe-branch issue="123"
$acme-cmd-prepare-git-recipe-branch issue="123" branch="feature/0.0_#123_example/00_work_item"
```
