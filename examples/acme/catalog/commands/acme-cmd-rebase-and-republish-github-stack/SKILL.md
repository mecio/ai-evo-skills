---
name: acme-cmd-rebase-and-republish-github-stack
description: Orchestra il rebase verificato, la ripubblicazione autorizzata e la registrazione 04r dello stack.
metadata: { ai-evo-kind: command, ai-evo-version: "1.0", ai-evo-recipe-only: false }
---

# Rebase e registrazione della ripubblicazione

## Purpose

Fornire alla recipe un'unica operazione condizionale: conservare invariati simulazioni e blocchi del comando di
rebase, oppure registrare nel worklog la ripubblicazione soltanto dopo un push verificato.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.git-stack-rebase-and-republish, git.remote-write]
  deny-capabilities: [github.remote-write]
inputs:
  issue: { required: true, description: "Issue proprietaria dello stack pubblicato." }
  publication_authorized: { required: true, description: "false esegue soltanto la simulazione; solo true autorizza push e registrazione 04r." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-rebase-and-republish-github-stack run '<JSON>'`. Il comando invoca
`acme-rebase-git-stack` con gli stessi input e ne restituisce invariati report, simulazioni, conflitti e blocchi.

Solo quando `publication_authorized` è true e il rebase autorizzato termina con `stack-republish-required`,
invoca `acme-republish-rebased-git-stack`, quindi rilancia il report e restituisce il nuovo stato del workflow.

## Expected output

JSON valido rispetto allo stesso contratto del comando di rebase: report del workflow, simulazione, conflitto o
diagnostica bloccante.

## Constraints

Non registrare una ripubblicazione dopo una simulazione o una diagnosi bloccante. Non eseguire operazioni GitHub,
submit, merge remoto o push ulteriori rispetto a quello atomico effettuato dal comando di rebase.

## Success criteria

Con autorizzazione false nessun branch o ref remoto viene modificato. Con autorizzazione true, un rebase riuscito
viene pubblicato, registrato in 04r e seguito dal report che indica il prossimo passo.

## Examples

```text
$acme-cmd-rebase-and-republish-github-stack issue="12724" publication_authorized="false"
$acme-cmd-rebase-and-republish-github-stack issue="12724" publication_authorized="true"
```
