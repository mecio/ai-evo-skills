---
name: acme-cmd-create-github-issue-breakdown
description: Applica la label epic e crea sub-issue GitHub da una scomposizione approvata e autorizzata.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Creazione della scomposizione GitHub

## Purpose

Applica la label epic e crea sub-issue GitHub da una scomposizione approvata e autorizzata.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [github.remote-write]
inputs:
  breakdown: { required: true, description: "Piano di scomposizione approvato." }
```

## Procedure

Con `mode: single` restituisci una mappa senza modificare GitHub. Con `mode: stacked` non eseguire alcuna operazione GitHub e restituisci una mappa con `parent_issue` e `layers`: ogni layer mantiene `id`, `title`, `body`, `dependencies`, l'ordine numerico in `sequence` ed eventuale `existing_branch`.

Con `mode: epic` richiedi `remote_authorized: true` e risolvi `<owner>/<repo>` esclusivamente con
`.ai-evo/bin/ai-evo-github-read repo-view`, mai dal remote Git. Verifica in lettura che la label esista con
`gh api repos/<owner>/<repo>/labels/epic`. Prima di ogni scrittura remota mostra la tabella prescritta dalle
direttive, con target, comando, effetto remoto, dati o metadati coinvolti e ripristino possibile, e attendi la
conferma esplicita riferita a quel solo comando.

Applica quindi la label senza rimuovere quelle esistenti con:

```bash
gh api -X POST repos/<owner>/<repo>/issues/<n>/labels -f "labels[]=epic"
```

Per ciascun item, nell'ordine delle dipendenze, scrivi titolo e corpo approvati in file temporanei privati (per
esempio con `umask 077` e `mktemp`) e non passarli inline. Scrivi il titolo senza newline finale, per esempio con
`printf '%s' "<titolo>" > <file-titolo>`. Mostra una tabella e ottieni una conferma prima di creare la issue:

```bash
gh api -X POST repos/<owner>/<repo>/issues -F title=@<file-titolo> -F body=@<file-body>
```

Dalla risposta conserva sia `number` sia `id`: `id` è l'identificatore interno e non coincide con il numero.
Mostra poi una nuova tabella e ottieni una nuova conferma prima di collegare quella issue al padre:

```bash
gh api -X POST repos/<owner>/<repo>/issues/<padre>/sub_issues -F sub_issue_id=<id>
```

Include nel corpo riferimenti alle dipendenze già create. Se il collegamento fallisce, riporta la issue creata ma non
collegata e non ritentare automaticamente. Alla fine rileggi con
`gh api repos/<owner>/<repo>/issues/<padre>/sub_issues` e verifica l'elenco. Non ripetere automaticamente nessuna
scrittura remota fallita.

## Expected output

Mappa JSON con numero e URL della issue principale e delle sub-issue create. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Con mode single o stacked non modificare GitHub; non ripetere automaticamente scritture fallite.

## Success criteria

Ogni sub-issue creata corrisponde a un item approvato e le dipendenze sono preservate.

## Examples

```text
$acme-cmd-create-github-issue-breakdown
```
