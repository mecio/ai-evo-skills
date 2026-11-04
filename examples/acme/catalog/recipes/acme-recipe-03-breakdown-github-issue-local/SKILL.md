---
name: acme-recipe-03-breakdown-github-issue-local
description: Scompone e registra localmente una issue senza creare sub-issue o modificare GitHub.
metadata: { ai-evo-kind: recipe, ai-evo-version: "1.0" }
---

# Scomposizione locale di una issue GitHub

## Purpose

Produrre e registrare un breakdown `single` o `stacked` per un workflow che vieta effetti remoti.

## Interface

Input, step e output sono definiti in [recipe.yaml](recipe.yaml). Il supervisor riceve gli input canonici dal
report della recipe 03 e aggiunge `allowed_modes` dalla propria policy.

## Procedure

Pianificare con `.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-03-breakdown-github-issue-local --adapter <adapter-corrente>`
e gli input strutturati forniti dal supervisor. Guidare il piano con `recipe advance` e conservare integralmente
gli output. Il comando di breakdown può scegliere soltanto i modi elencati in `allowed_modes`; se l'analisi
richiede una epic con sub-issue autonome deve fermarsi, così il supervisor produce un handoff. Il piano approvato
viene registrato direttamente nel worklog senza invocare il comando di creazione GitHub.

## Expected output

La ricevuta del breakdown locale persistito sotto la sessione 03.

## Constraints

Non creare issue, label, branch o altri artefatti remoti. Non trasformare una epic necessaria in una struttura
single o stacked per evitare l'handoff.

## Success criteria

Il worklog contiene una scomposizione `single` o `stacked` valida e il report può proporre la fase locale seguente.

## Examples

```text
$acme-recipe-03-breakdown-github-issue-local
```
