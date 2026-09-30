---
name: acme-cmd-configure-git-stack-upstreams
description: Verifica ref e OID remoti dello stack appena pubblicato e configura gli upstream locali omonimi.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Configurazione degli upstream di uno stack Git

## Purpose

Collegare ogni branch locale pubblicato al branch omonimo sul remote soltanto dopo avere verificato che i due
OID coincidano.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: enabled
inputs:
  publication_report: { required: true, description: "Rapporto riuscito di acme-cmd-push-git-stacked-stack." }
```

## Procedure

1. Richiedere un `publication_report` riuscito e verificare worktree pulita, stack locale attivo e configurazione
   `ensure_upstream_after_publish: true` in `skills/config/acme-git-branches.yaml`. Se il flag è `false`,
   restituire `skipped: upstream-not-required` senza modificare la configurazione Git.
2. Leggere `stack_remote` dalla stessa configurazione; non dedurre il remote dal branch corrente. Creare una
   directory temporanea privata sotto `/tmp` e generare il manifest con
   `.ai-evo-prj/scripts/acme-git-stack-upstreams inspect --remote <stack_remote> --output <manifest>`.
3. Controllare che ogni entry del manifest sia eleggibile: il ref remoto deve esistere e il suo OID deve coincidere
   con l'OID locale. Se anche una entry non è eleggibile, non invocare `apply`, riportare il manifest e fermarsi
   senza configurare upstream parziali.
4. Eseguire `.ai-evo-prj/scripts/acme-git-stack-upstreams apply --manifest <manifest>`. L'helper ricontrolla
   stack, URL del remote e OID prima di impostare `branch.<nome>.remote` e `branch.<nome>.merge`.
5. Riportare manifest di ispezione, risultato dell'applicazione e upstream finale di ogni branch. In caso di
   errore, conservare la diagnostica e non ripetere automaticamente il push né l'applicazione.

## Expected output

Rapporto con remote, branch ispezionati, OID locale e remoto, upstream configurati oppure motivo dello skip o
del fallimento.

## Constraints

- Non eseguire push, submit, pull request, rebase o merge.
- Non configurare un upstream se ref remoto e OID locale non coincidono.
- Non cambiare remote, nomi dei branch o metadati dello stack.

## Success criteria

Ogni branch dello stack pubblicato traccia soltanto il branch omonimo verificato sul `stack_remote` configurato.

## Examples

```text
$acme-cmd-configure-git-stack-upstreams publication_report="<push riuscito>"
```
