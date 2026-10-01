---
name: acme-cmd-republish-rebased-git-stack
description: Registra nel worklog una ripubblicazione già eseguita dopo il rebase di uno stack.
metadata: { ai-evo-kind: command, ai-evo-version: "1.0", ai-evo-recipe-only: false }
---

# Registrazione della ripubblicazione di uno stack

## Purpose

Conservare un nuovo checkpoint `publish_branch` immutabile dopo un rebase e push manuali verificati.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.git-record-republication]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Issue proprietaria dello stack pubblicato." }
  publication_authorized: { required: true, description: "Deve essere letteralmente true; attesta il push manuale già autorizzato." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-republish-rebased-git-stack republish '<JSON>'` con `issue` e
`publication_authorized: true`. Il comando richiede worktree pulita, aggiorna i ref remoti e richiede che ogni
branch locale coincida con il suo upstream. Verifica la linearità della catena e l'uguaglianza della sequenza di
`git patch-id --stable` fra i commit pubblicati in precedenza e quelli ribasati. Non esegue push.

Solo dopo tutte le verifiche registra per ogni layer una nuova sessione `04r-republish-attempt-01` con un checkpoint
`publish_branch`; conserva `previous_remote_oid`, `previous_base_oid` e `patch_ids_equivalent: true` senza toccare
i checkpoint originali.

## Expected output

JSON con i layer ripubblicati e i nuovi OID remoti.

## Constraints

Non esegue `gh stack push`, `gh stack sync`, rebase, merge o push. Se patch-id, upstream o linearità non coincidono,
non scrive checkpoint.

## Success criteria

`published_layers()` seleziona i nuovi checkpoint e un successivo `prepare` riconosce lo stack lineare.

## Examples

```text
$acme-cmd-republish-rebased-git-stack issue="12603" publication_authorized="true"
```
