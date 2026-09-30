---
name: acme-cmd-adopt-github-issue-layer
description: Verifica e adotta nel worklog un layer stacked già implementato localmente.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Adozione di un layer GitHub già implementato

## Purpose

Verifica un layer stacked già implementato e produce l'evidenza da registrare come checkpoint 04.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  issue: { required: true, description: "Numero della issue principale." }
  layer: { required: true, description: "JSON del layer stacked da adottare." }
  branch: { required: true, description: "Branch locale già implementato." }
```

## Procedure

Richiedi una conferma esplicita dello sviluppatore prima di eseguire l'adozione. Da worktree pulita verifica in sola lettura che il branch e il suo parent esistano nello stack locale, che il trunk sia coerente, e che nell'intervallo `parent..branch` esista almeno un commit con soggetto `#<issue> `. Non creare branch, commit, push o risorse GitHub. Restituisci un JSON con `origin: "pre-existing"`, `layer_id`, `branch`, `parent_branch`, `base_branch` e i commit verificati. La recipe chiamante registra tale risultato come checkpoint 04 completo.

## Expected output

Un JSON conforme a [references/output.schema.json](references/output.schema.json), con le coordinate del layer e tutti i commit verificati.

## Constraints

Non modificare Git o GitHub. L'adozione richiede l'approvazione esplicita dello sviluppatore e una worktree pulita.

## Success criteria

Il branch, il parent, il trunk e almeno un commit della issue sono verificati, così la recipe può salvare il checkpoint 04 completo.

## Examples

```text
$acme-cmd-adopt-github-issue-layer issue="12549" layer='<layer L0>' branch=".../00_countryresolution"
```
