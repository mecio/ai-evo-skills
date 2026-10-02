---
name: acme-cmd-submit-github-stack-prs
description: Crea o aggiorna come draft le pull request di uno stack pubblicato, poi sincronizza titoli e descrizioni con il lavoro svolto.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Submit delle pull request di uno stack GitHub

## Purpose

Creare o aggiornare le pull request collegate di uno stack pubblicato, mantenerle tutte in draft e descrivere per
ciascun layer le modifiche e le verifiche effettivamente svolte.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [git.remote-write, github.remote-write]
inputs:
  publication_report: { required: true, description: "Rapporto riuscito della recipe 07 con branch pubblicati e upstream configurati." }
  verification_report: { required: true, description: "Report `verified` della recipe 05 o `accepted` della recipe 06." }
  submit_authorized: { required: true, description: "Deve essere letteralmente true; conferma la creazione o l'aggiornamento remoto delle PR." }
```

## Procedure

1. Accettare `submit_authorized` soltanto se è letteralmente `true`; altrimenti fermarsi senza operazioni remote.
   Verificare `publication_report`, `verification_report`, worktree pulita, stack locale attivo e upstream di ogni
   branch. Non dedurre uno stack o una repository alternativi.
2. Prima di `gh stack submit --auto`, mostrare la tabella prescritta dalle direttive con repository, branch, comando,
   PR che possono essere create o aggiornate, effetto e ripristino possibile; attendere la conferma esplicita per
   quel solo submit. Usare `--auto` perché evita l'editor interattivo e crea le nuove pull request come draft; non
   usare `--open`. Il comando crea le PR mancanti, aggiorna quelle esistenti e collega le loro basi nello stack.
3. Risolvere una sola volta `<owner>/<repo>` con `.ai-evo/bin/ai-evo-github-read repo-view`; non derivarlo dal
   remote Git. Per ogni branch dello stack, individuare una sola PR aperta con `gh pr list --head <branch> --state open`.
   Fermarsi se manca o è ambigua. Prima di ogni eventuale `gh pr ready <url> --undo`, mostrare una nuova tabella e
   attendere la conferma esplicita per quella sola conversione a draft. Se il comando fallisce con l'errore GraphQL
   relativo a Projects (classic), documentare nel rapporto l'alternativa `gh api graphql` con la mutation
   `convertPullRequestToDraft`, senza eseguirla automaticamente.
4. Generare titolo e descrizione dai fatti locali del solo layer, confrontando `parent..branch`: il titolo è una
   sintesi concisa dei commit del layer e conserva il numero della issue quando presente; la descrizione Markdown
   contiene `## Cosa cambia` con le modifiche osservate, `## Verifiche` con le evidenze del report e `## Stack` con
   branch e base. Non dichiarare test, issue o comportamenti non dimostrati. Non includere token, credenziali,
   istruzioni della conversazione o diff completi.
5. Scrivere ogni titolo e body in file temporanei privati (per esempio con `umask 077` e `mktemp`); non passarli mai
   inline. Scrivere il titolo senza newline finale, per esempio con `printf '%s' "<titolo>" > <file-titolo>`.
   Prima di ogni PATCH, mostrare una nuova tabella con target, comando, effetto remoto, dati o metadati coinvolti e
   ripristino possibile; includere URL, titolo e sintesi della descrizione. Attendere la conferma esplicita per quel
   solo comando, poi eseguire esclusivamente:

   ```bash
   gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F title=@<file-titolo> -F body=@<file-body>
   ```

   Il PATCH contiene soltanto `title` e `body`. Dopo ogni PATCH riuscito, rileggere con
   `gh api repos/<owner>/<repo>/pulls/<n>` e verificare che `title`, `body`, `draft` e `base.ref` corrispondano ai
   valori attesi; riportare URL, stato draft, titolo e base risultanti. Se un submit, PATCH o rilettura fallisce,
   conservare la diagnostica e non ritentare automaticamente.

## Expected output

Rapporto con tutte le PR dello stack, URL, branch, base, stato draft, titolo e descrizione applicati, oltre alle
evidenze usate per comporli.

## Constraints

- Usare `gh stack submit --auto`, mai `--open` né submit interattivo.
- Tutte le PR create o aggiornate devono risultare draft.
- Modificare soltanto titolo, descrizione e stato draft delle PR appartenenti allo stack attivo.
- Non aggiungere reviewer, assegnatari, label, milestone, commenti, approvazioni o merge.

## Success criteria

Ogni branch dello stack ha una sola pull request aperta, collegata al parent corretto, in draft e con metadati
derivati dal suo diff incrementale e dalle evidenze di verifica.

## Examples

```text
$acme-cmd-submit-github-stack-prs submit_authorized="true"
```
