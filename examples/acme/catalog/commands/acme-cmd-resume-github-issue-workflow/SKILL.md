---
name: acme-cmd-resume-github-issue-workflow
description: Applica il recupero richiesto dal report e restituisce il prossimo stato del workflow.
metadata: { ai-evo-kind: command, ai-evo-version: "1.0", ai-evo-recipe-only: false }
---

# Ripresa orchestrata del workflow

## Purpose

Riunire nella recipe di ripresa il checkout del branch e la registrazione della ripubblicazione dopo rebase.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.workflow-resume]
inputs:
  issue: { required: true, description: "Issue del workflow da riprendere." }
  publication_authorized: { default: "false", description: "true autorizza soltanto la registrazione della ripubblicazione già eseguita manualmente." }
```

## Procedure

Esegue prima il report. Per `branch-recovery-required` recupera il branch con `prepare` e rilancia il report. Per
`stack-republish-required` esegue `acme-cmd-republish-rebased-git-stack` solo con
`publication_authorized: true`, poi rilancia il report. Restituisce invariato il report risultante.

## Expected output

Il JSON del report dopo il recupero o la registrazione.

## Constraints

Non esegue rebase, merge, `gh stack sync` o push.

## Success criteria

Lo sviluppatore invoca una sola recipe di raccordo e riceve il prossimo stato reale del workflow.

## Examples

```text
$acme-cmd-resume-github-issue-workflow issue="12603" publication_authorized="true"
```
