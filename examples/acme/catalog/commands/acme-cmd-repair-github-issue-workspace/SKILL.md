---
name: acme-cmd-repair-github-issue-workspace
description: Ripristina tooling e runtime di una worktree isolata già assegnata a una issue.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Riparazione workspace issue

## Purpose

Ripristinare i collegamenti AI Evo gestiti quando il coordinator è cambiato.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.issue-workspace-repair]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero della issue." }
  worklog_session_name: { required: true, description: "Una sessione canonica del tentativo assegnato." }
```

## Procedure

Dalla checkout coordinatrice eseguire la capability con `issue` e `worklog_session_name`. L'helper legge il
manifesto immutabile del tentativo, verifica coordinator e worktree registrati, poi riallinea `.ai-evo`,
`.ai-evo-prj`, `.ai-evo-skills.yaml`, `.ai-evo-work` e i target delle skill disponibili. Non gestisce runtime,
dipendenze o tooling applicativi.

## Expected output

Il manifesto aggiornato con provisioning e data UTC della riparazione. Per `workspace_mode: current` restituisce
`repair: not-required` senza modificare il checkout.

## Constraints

Non cambia branch, commit, worklog o riferimenti remoti e non sostituisce risorse locali non gestite.

## Success criteria

La worktree assegnata usa di nuovo tooling e dipendenze coerenti con il coordinator registrato.

## Examples

```text
$acme-cmd-repair-github-issue-workspace issue="12637" worklog_session_name="issue-12637/attempt-01/05-review-attempt-01"
```
