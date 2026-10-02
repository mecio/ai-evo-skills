---
name: acme-cmd-push-git-stacked-branch
description: Pubblica e collega al remote il branch stacked appena implementato, senza creare pull request.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Pubblicazione immediata di un branch stacked

## Purpose

Conservare sul remote il primo stato commitato di un singolo layer, così il lavoro può essere ripreso da un'altra
worktree senza dipendere dai soli metadati locali o dal worklog.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [git.remote-write]
  deny-capabilities: [github.remote-write]
inputs:
  implementation_report: { required: true, description: "Output riuscito di acme-cmd-implement-github-issue con branch e commit del layer." }
```

## Procedure

1. Verificare che `implementation_report` sia riuscito, identifichi un solo `branch` locale e contenga almeno un
   commit. Da worktree pulita, verificare che `HEAD` sia quel branch e che il suo OID coincida con l'ultimo commit
   riportato.
2. Dalla root Git eseguire `.ai-evo-prj/scripts/acme-git-local push-branch '<JSON>'`, con il solo campo
   `implementation_report`. L'helper risolve `stack_remote` dal percorso canonico
   `.ai-evo-prj/skills/config/acme-git-branches.yaml`; non dedurre il remote dal branch corrente.
   Verificare che il remote esista e che il parent dichiarato dal report sia disponibile localmente.
3. L'helper esegue una sola pubblicazione non forzata del branch corrente sul ref remoto omonimo e imposta il suo
   upstream. Non usare comandi Git o gh aggiuntivi.
4. Prima del push registrare l'OID del parent come `parent_oid`; per il primo layer registrarlo anche come
   `base_oid`. Leggere il ref remoto e verificarne l'OID rispetto a `HEAD`; se non coincidono, segnalare l'errore
   senza ritentare. Restituire branch, `parent_branch`, `base_branch`, `sequence`, remote, OID locale/remoto,
   `parent_oid`, `base_oid` quando applicabile e upstream configurato. `base_branch` e `sequence` descrivono la
   posizione del layer già contenuta nel report di implementazione; per un solo layer `sequence` è `0`.

## Expected output

Rapporto con branch pubblicato, remote, OID verificati e upstream locale. Il rapporto costituisce l'evidenza di
recuperabilità della worktree.

## Constraints

- È consentito solo dopo un'implementazione riuscita con almeno un commit.
- Pubblica un solo branch per invocazione e non crea né aggiorna pull request.
- Non modificare nomi, parent, metadati dello stack o altri branch remoti.
- Se il push fallisce, conservare la diagnostica e non ritentare automaticamente.

## Success criteria

Il branch locale appena implementato ha un ref omonimo sul remote configurato, con lo stesso OID, e lo traccia come
upstream.

## Examples

```text
$acme-cmd-push-git-stacked-branch implementation_report="<implementazione riuscita>"
```
