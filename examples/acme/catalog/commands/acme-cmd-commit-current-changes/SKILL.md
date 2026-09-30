---
name: acme-cmd-commit-current-changes
description: >-
  Applica un piano ready e crea un singolo commit locale con le modifiche correnti esatte. Non prepara il piano,
  non modifica contenuti e non verifica la struttura dello stack.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Applicazione del commit pianificato

## Purpose

Creare il commit descritto da un piano già validato, fallendo se branch, OID o modifiche non coincidono più.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: auto
  capabilities: [acme.git-commit]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  commit_plan:
    description: Piano prodotto da acme-cmd-prepare-commit-current-changes.
    required: true
```

## Procedure

1. Con un handoff risolto eseguire direttamente dal passaggio 2; altrimenti pianificare il comando e applicare
   modalità, policy, input e profilo ricevuti.
2. Richiedere un piano conforme a
   `.ai-evo-prj/skills/catalog/commands/acme-cmd-prepare-commit-current-changes/references/output.schema.json`.
   Non ricostruire campi mancanti. Con `skipped` restituire invariati `status` e `reason`, senza scritture.
3. Per un piano ready, dalla root applicativa eseguire `.ai-evo-prj/scripts/acme-git-local commit '<JSON>'`,
   passando il piano integrale come un solo argomento JSON quotato come dato. Non eseguire `git add` o
   `git commit` direttamente né aggiungere opzioni all'helper.
4. L'helper rivalida messaggio, branch, OID, identità, percorsi e digest prima di toccare l'indice. Aggiunge
   soltanto i file previsti, verifica i contenuti staged e crea un solo commit con il messaggio approvato,
   mantenendo gli hook configurati. Non offre amend, push, configurazione Git o bypass degli hook.
5. Propagare output ed errori invariati. Un errore dopo lo staging può lasciare effetti locali: conservarne
   la diagnostica e verificare lo stato prima di riprovare, senza reset o secondo commit automatico.
6. Sul successo restituire il JSON dell'helper con `status: committed`, `oid`, `branch` e `issue`.
   La verifica strutturale dello stack appartiene al comando successivo.

## Expected output

Output conforme a [references/output.schema.json](references/output.schema.json). Il motore estrae un solo
documento JSON e lo valida prima della consegna; testo accessorio attorno a un unico blocco fenced è
accettato, mentre candidati multipli, JSON malformato o violazioni dello schema fanno fallire lo step.
Gli artefatti nativi e la diagnostica devono essere conservati.

Un JSON con `status: committed` e l'OID creato, oppure lo stato `skipped` ricevuto dal piano.

## Constraints

- Non reinterpretare o aggiornare il piano durante l'esecuzione.
- Non modificare i contenuti dei file o la configurazione Git.
- Non eseguire amend, push, tag, branch, release o bypass degli hook.

## Success criteria

- Il commit viene creato dal medesimo stato e con i medesimi contenuti fissati nel piano.
- Git e gli hook terminano correttamente.

## Examples

```text
$acme-cmd-commit-current-changes commit_plan="<json ready>"
```
