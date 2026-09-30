---
name: acme-cmd-prepare-commit-current-changes
description: >-
  Prepara e valida il piano di un singolo commit per tutte le modifiche locali correnti. Opera in sola lettura,
  non modifica l'indice e non crea il commit.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Preparazione del commit delle modifiche correnti

## Purpose

Fissare branch, OID iniziale, file, contenuti e messaggio che il comando di commit dovrà applicare senza
reinterpretare le modifiche.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: auto
  capabilities: [acme.git-inspect, acme.git-validate-message]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  work_specification:
    description: Specifica ready opzionale dalla quale ricavare la issue del layer.
    default: ""
  issue:
    description: Numero intero positivo della issue, con o senza il prefisso #; se vuoto ricavarlo dal branch quando univoco.
    default: ""
  allow_no_changes:
    description: Se true, produrre un piano skipped quando la worktree è pulita; usare false nei layer stacked.
    default: "false"
```

## Procedure

1. Con un handoff risolto eseguire direttamente dal passaggio 2; altrimenti pianificare il comando e applicare
   modalità, policy, input e profilo ricevuti.
2. Dalla root applicativa eseguire `.ai-evo-prj/scripts/acme-git-local inspect`. L'helper legge branch, OID,
   identità Git e file modificati/non tracciati con digest; esclude gli ignorati e rifiuta submodule modificati.
   Per leggere diff e storia usare il wrapper di lettura Git consentito, non Bash generico.
3. Se `work_specification` è valorizzata, richiedere stato ready e ricavarne la issue; se anche `issue` è
   valorizzata richiederne la coincidenza. Accettare un intero positivo con eventuale `#`; se mancante,
   ricavarlo dal branch solo quando univoco. Non ricostruire identità o stato mancanti.
4. Senza modifiche restituire soltanto `status: skipped` e `reason`, esclusivamente con `allow_no_changes=true`;
   altrimenti fallire. Esaminare integralmente il diff e preparare in italiano titolo `#<numero> <titolo>`
   lungo al massimo 72 caratteri e un corpo che copra tutti i file, senza trailer, firme o attribuzioni all'AI.
5. Eseguire `.ai-evo-prj/scripts/acme-git-local validate-message '<JSON>'` con i soli campi `issue` intera
   positiva e `message` completo, in un singolo argomento JSON quotato come dato. L'helper valida in memoria,
   senza file temporanei, e non crea commit. Propagare gli errori; non aggirare il validatore.
6. Restituire `status: ready`, `issue`, i campi invariati `branch`, `initial_oid`, `git_identity` e `files`
   della fotografia, quindi `summary`, `risks`, `missing_verifications` e `message` validato. Ogni file ha
   `path`, `change` (`added`, `modified`, `deleted`) e `sha256` dei contenuti; per cancellazioni il digest è null.
   I rename sono cancellazione e aggiunta. Non modificare indice, file o configurazione.

## Expected output

Output conforme a [references/output.schema.json](references/output.schema.json). Il motore estrae un solo
documento JSON e lo valida prima della consegna; testo accessorio attorno a un unico blocco fenced è
accettato, mentre candidati multipli, JSON malformato o violazioni dello schema fanno fallire lo step.
Gli artefatti nativi e la diagnostica devono essere conservati.

Un piano JSON autosufficiente con `status: ready`, oppure `status: skipped` nel solo caso autorizzato senza
modifiche.

## Constraints

- Includere tutte e sole le modifiche locali censite.
- Non modificare indice, file o configurazione Git.
- Non chiedere approval: la recipe decide se e quando applicare il piano.

## Success criteria

- Il piano identifica senza ambiguità stato iniziale, contenuti e messaggio del commit.
- Il messaggio rispetta issue, lingua, lunghezza e divieto di attribuzione all'AI.

## Examples

```text
$acme-cmd-prepare-commit-current-changes issue="1234" allow_no_changes="false"
```
