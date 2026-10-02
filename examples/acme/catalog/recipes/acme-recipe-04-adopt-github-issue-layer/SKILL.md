---
name: acme-recipe-04-adopt-github-issue-layer
description: Registra come checkpoint 04 un layer stacked implementato prima del workflow.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Adozione di un layer preesistente

## Purpose

Registra come checkpoint 04 un layer `stacked` implementato prima del workflow.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Per percorsi worklog e lineage consultare la [guida alle recipe](../../../acme-recipes.md).

## Procedure

Usa questa recipe solo quando il resolver rileva un branch di un layer già implementato senza checkpoint 04 e lo sviluppatore ha approvato esplicitamente l'adozione. Verifica branch, parent, il trunk risolto per il contesto della worktree da `acme-worktree-context`, commit della issue e worktree pulita senza effettuare scritture remote; il risultato con `origin: pre-existing` viene registrato come checkpoint 04 completo nel worklog del layer.

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-04-adopt-github-issue-layer --adapter <adapter-corrente>` e gli input ricevuti. Seguire il protocollo di `.ai-evo/docs/recipe-runtime.md`, eseguire solo lo step risolto e fermarsi al primo errore.

## Expected output

Il valore `outputs.result` definito in `recipe.yaml`, conservato integralmente nella sessione del layer.

## Constraints

Richiede l'approvazione esplicita dello sviluppatore. Non crea branch, commit, push o risorse GitHub.

## Success criteria

Il checkpoint 04 del layer contiene `origin: "pre-existing"` e le coordinate Git verificate.

## Examples

```text
$acme-recipe-04-adopt-github-issue-layer issue="12549" layer='<layer L0>' branch=".../00_countryresolution"
```
