---
name: acme-cmd-squash-git-stack-preview
description: Crea un branch locale temporaneo con un solo commit e l'albero finale di uno stack o branch Acme.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Preview squash locale di uno stack Git

## Purpose

Produrre un raccordo locale, temporaneo e senza checkout per revisionare velocemente il risultato complessivo di
un branch o di uno stack rispetto al trunk configurato.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.git-squash-stack-preview]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero della issue associata al branch o allo stack." }
  working_directory: { default: "", description: "Root Git; vuoto usa la worktree registrata dal worklog dell'issue." }
  branch: { default: "", description: "Branch locale sorgente; vuoto usa la punta registrata dal workflow o dal worklog." }
  preview_branch: { default: "", description: "Branch locale temporaneo; vuoto usa tmp/<issue>-squash." }
  replace_existing: { default: "false", description: "true sostituisce il branch solo se è già una preview della stessa issue." }
```

## Procedure

1. Dalla checkout coordinatrice eseguire
   `.ai-evo-prj/scripts/acme-squash-git-stack-preview create '<JSON>'`, passando tutti gli input come un unico
   oggetto JSON quotato. Restituire invariato il JSON prodotto.
2. Se `working_directory` è vuota, l'helper usa la worktree registrata per l'attempt più recente della issue;
   altrimenti richiede che identifichi esattamente una root Git. Se `branch` è vuoto, legge il branch più recente
   dal worklog senza dedurlo dal nome o dal branch corrente.
3. L'helper legge `stack_remote` e il trunk del contesto da `skills/config/acme-git-branches.yaml`, verifica in
   sola lettura worktree pulita, branch sorgente locale, merge-base e disponibilità di `preview_branch`.
   `replace_existing=true` è ammesso soltanto se il primo paragrafo del commit esistente coincide con quello della
   preview della stessa issue e il branch non ha upstream.
4. Crea con `git commit-tree` un solo commit, figlio del merge-base e con l'albero della punta sorgente, quindi il
   branch locale senza checkout. Verifica albero identico, singolo commit sopra la base, shortstat, assenza di
   upstream e invarianza di branch corrente, `HEAD`, indice e worktree. In caso di errore dopo la creazione,
   elimina il nuovo branch oppure ripristina atomicamente l'OID precedente.

## Expected output

Un JSON conforme a [references/output.schema.json](references/output.schema.json), con coordinate della preview,
statistiche, comandi suggeriti per la review e comando locale di pulizia.

## Constraints

- Non esegue checkout, rebase, amend, reset, push, `gh stack` o operazioni Git/GitHub remote.
- Non modifica branch dello stack, worklog, upstream, indice o contenuti della worktree.
- Il commit non contiene righe `Co-Authored-By`; il branch di preview non riceve upstream.
- Un branch di preview esistente non viene mai sovrascritto senza `replace_existing=true` e verifica del messaggio.

## Success criteria

Il branch temporaneo contiene esattamente un commit sopra il merge-base, ha lo stesso albero della sorgente e può
essere eliminato con il comando restituito senza aver cambiato la checkout corrente.

## Examples

```text
$acme-cmd-squash-git-stack-preview issue="12822"
$acme-cmd-squash-git-stack-preview issue="12822" branch="feature/.../01_layer" preview_branch="tmp/12822-l1-squash"
```
