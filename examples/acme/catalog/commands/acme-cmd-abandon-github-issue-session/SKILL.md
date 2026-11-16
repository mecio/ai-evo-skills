---
name: acme-cmd-abandon-github-issue-session
description: Chiude esplicitamente una sessione locale active rimasta incompleta, purché non abbia prodotto effetti remoti.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Abbandono di una sessione locale

## Purpose

Rendere terminale una sessione `active` che non deve essere ripresa, conservandone motivo e cronologia senza
cancellare checkpoint o artefatti.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.workflow-session-abandon]
inputs:
  issue: { required: true, description: "Numero della issue proprietaria della sessione." }
  session_name: { required: true, description: "Percorso canonico completo della sessione active." }
  reason: { required: true, description: "Motivo non vuoto dell'abbandono." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-abandon-github-issue-session abandon '<JSON>'`, passando esattamente `issue`,
`session_name` e `reason`. Restituisci invariato il JSON prodotto.

## Expected output

JSON conforme a [references/output.schema.json](references/output.schema.json), con sessione, motivo e timestamp
dell'abbandono registrato.

## Constraints

Il comando modifica soltanto `session.json` e `context.md` sotto il worklog. Rifiuta sessioni già terminali,
path non canonici, link simbolici interni e sessioni con uno step remoto riuscito (`publish_branch`,
`configure_upstreams` o `submit_stack`). Non modifica Git né GitHub.

## Success criteria

La sessione ha stato `abandoned`, motivo e timestamp coerenti; il writer del worklog rifiuta nuovi record.

## Examples

```text
$acme-cmd-abandon-github-issue-session issue="12553" session_name="issue-12553/attempt-01/04-implement-attempt-01" reason="Piano sostituito"
```
