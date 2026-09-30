---
name: acme-cmd-breakdown-github-issue
description: Decide con lo sviluppatore se un’issue va scomposta e prepara sub-issue autonome, senza modificare GitHub.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Scomposizione di una issue GitHub

## Purpose

Decide con lo sviluppatore se un’issue va scomposta in sub-issue autonome o in layer stacked, senza modificare GitHub.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-only
  network: disabled
inputs:
  issue_analysis: { required: true, description: "Analisi tecnica ready della issue principale." }
```

## Procedure

Ricevi l’analisi tecnica pronta della issue. Valuta coesione, dipendenze, confini di modifica, verificabilità e
valore di consegna. Se il lavoro è unitario restituisci `mode: single`. Suggerisci `stacked` quando i lavori sono
sequenziali sullo stesso componente e non hanno valore di consegna autonomo: `items` contiene almeno due layer
`L0`, `L1`, … con obiettivo, perimetro, criteri e test previsti nel `body`, dipendenze dai layer precedenti e,
se noto, `existing_branch`; `remote_authorized` resta `false`. Suggerisci `epic` solo quando i lavori hanno valore
di consegna, ownership o tempi indipendenti; in quel caso proponi sub-issue autosufficienti. Discuti una decisione
alla volta e fai approvare elenco e ordine; per l'epic chiedi separatamente l’autorizzazione remota. Non creare issue né applicare label.

## Expected output

Piano JSON approvato con mode single oppure epic e sub-issue ordinate. Restituire solo JSON conforme a `references/output.schema.json`.

## Constraints

Non creare issue né applicare label durante la progettazione.

Per leggere file locali usare uno strumento di sola lettura, preferibilmente il reader nativo dell'executor.
Non usare opzioni di modifica in-place, inclusi `sed -i`, `perl -i` ed equivalenti: anche in una fase di
sola lettura tali opzioni scrivono nel file e possono richiedere un'autorizzazione, soprattutto quando il
percorso risolve un symlink esterno alla worktree autorizzata.

## Success criteria

La scomposizione è approvata e distingue approvazione del piano e autorizzazione remota.

## Examples

```text
$acme-cmd-breakdown-github-issue
```
