---
name: acme-cmd-push-git-stacked-stack
description: Pubblica i branch di uno stack locale verificato con gh stack push, senza creare o aggiornare pull request.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Pubblicazione di uno stack Git

## Purpose

Pubblica i branch di uno stack locale verificato con gh stack push, senza creare o aggiornare pull request.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [git.remote-write]
  deny-capabilities: [github.remote-write]
inputs:
  verification_report: { required: true, description: "Report `verified` della recipe 05 o `accepted` della recipe 06 per lo stack da pubblicare." }
  publication_authorized: { required: true, description: "Deve essere letteralmente true; conferma il push remoto richiesto dallo sviluppatore." }
```

## Procedure

Accettare `publication_authorized` soltanto se è letteralmente `true`; altrimenti fermarsi senza operazioni remote. Verifica che `verification_report` attesti `verified` oppure `accepted`, che la worktree sia pulita e che il branch corrente appartenga allo stack verificato. Prima di `gh stack push`, mostrare la tabella prescritta dalle direttive con remote, branch dello stack, comando, effetto e ripristino possibile, quindi attendere la conferma esplicita per quel solo push. Esegui soltanto `gh stack push`; non usare `gh stack submit`, `gh pr`, `git push`, `sync`, `rebase` o altri comandi remoti. Riporta i branch pubblicati. La configurazione degli upstream appartiene al comando successivo. Se il push fallisce, conserva la diagnostica senza ripetere automaticamente e senza affermare che esistano PR.

## Expected output

Rapporto con branch pubblicati, oppure diagnostica del push fallito.

## Constraints

Usare soltanto gh stack push per pubblicare; non creare PR, non configurare upstream e non ritentare automaticamente.

## Success criteria

Lo stack verificato è pubblicato senza dichiarare PR inesistenti.

## Examples

```text
$acme-cmd-push-git-stacked-stack
```
