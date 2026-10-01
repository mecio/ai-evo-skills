---
name: acme-cmd-verify-git-stacked-branch
description: >-
  Verifica dopo i commit un singolo layer locale gh stack: branch corrente, parent, sequenza di commit, worktree
  pulita e struttura dello stack. Non modifica Git e non verifica i requisiti funzionali.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Verifica strutturale di un layer stacked

## Purpose

Bloccare la creazione del layer successivo quando il branch non coincide con manifest e stack.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: auto
  capabilities: [acme.git-verify-branch]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  work_specification:
    description: Specifica ready del work item con base, parent, branch e sequenza approvati.
    required: true
```

## Procedure

1. Con un handoff risolto eseguire direttamente dal passaggio 2; altrimenti pianificare il comando e applicare
   modalità, policy e profilo ricevuti.
2. Richiedere la specifica ready e ricavarne letteralmente `base_branch`, `parent_branch`, `branch`, `sequence`.
3. Dalla root applicativa eseguire `.ai-evo-prj/scripts/acme-git-local verify-branch '<JSON>'` con questi
   quattro campi come un solo argomento JSON quotato come dato. L'helper invoca `acme-git-stack-state`
   richiedendo base, parent, posizione, sequenza di commit, branch corrente in punta e worktree pulita.
4. Restituire il JSON invariato dell'helper: `status: verified`, `stack_state` integrale e la sequenza `commits`
   dal parent alla punta. Ogni commit contiene `oid`, `subject` e `files`. Non sovrascrivere
   `stack_state.status`, che descrive la worktree.
   Se `stack_state.rebase_required` è vero, l'helper fallisce con una diagnostica esplicita: un layer da ribasare
   sul trunk corrente non può essere verificato né usato per creare un layer figlio.
   Se l'output dell'helper non è conforme allo schema, fallire senza modificarlo. Propagare il primo errore senza correggere Git né rieseguire controlli alternativi.

## Expected output

Output conforme a [references/output.schema.json](references/output.schema.json), incluso `commit` come punta e `commits` come sequenza completa. Il motore estrae un solo
documento JSON e lo valida prima della consegna; testo accessorio attorno a un unico blocco fenced è
accettato, mentre candidati multipli, JSON malformato o violazioni dello schema fanno fallire lo step.
Gli artefatti nativi e la diagnostica devono essere conservati.

Un report JSON autosufficiente con stato `verified`, tutti i commit del layer e prove dello stack corrente.

## Constraints

- Sola lettura e nessuna rete.
- Almeno un commit nel layer; tutti devono essere successivi al parent dichiarato.
- Nessuna correzione, checkout, restack o pubblicazione.

## Success criteria

- Branch, parent, sequenza, commit, punta dello stack e worktree coincidono con gli input.

## Examples

```text
$acme-cmd-verify-git-stacked-branch work_specification="<ready con base, parent, branch e sequenza>"
```
