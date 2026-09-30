---
name: acme-cmd-save-worklog-output
description: Salva invariato l'output di un comando in una sessione .ai-evo-work e lo restituisce al chiamante.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Checkpoint di una recipe

## Purpose

Salva invariato l'output di un comando in una sessione .ai-evo-work e lo restituisce al chiamante.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.worklog-record]
inputs:
  session_name: { required: true, description: "Percorso relativo della sessione sotto .ai-evo-work." }
  recipe_name: { required: true, description: "Nome della recipe che produce il checkpoint." }
  session_input: { required: true, description: "JSON immutabile degli input della sessione." }
  step_name: { required: true, description: "Identificatore dello step registrato." }
  source_name: { required: true, description: "Nome del comando che ha prodotto il risultato." }
  outcome: { required: true, description: "Esito del comando sorgente da registrare." }
  output: { required: true, description: "Output integrale del comando sorgente, da preservare." }
  expected_output_sha256: { required: true, description: "SHA-256 dell'output, calcolato dal runtime della recipe." }
  error: { required: true, description: "Errore del comando sorgente oppure null." }
  artifact_name: { default: "", description: "Nome opzionale di un artefatto stabile da salvare nella sessione." }
  complete: { default: "false", description: "Indica se il checkpoint conclude la sessione." }
```

## Procedure

Il logger accetta **percorsi di file**, non valori inline, per `--session-input`, `--output`, `--error` e, quando ricevuto, `--work-context`. Crea una directory temporanea privata direttamente sotto `/tmp`, con nome `ai-evo-worklog-<identificatore>`, e al suo interno:

1. serializza `session_input` in `session-input.json` e `error` in `error.json` come JSON validi;
2. scrivi `output` invariato, compresi newline e spazi finali, in `output.txt`;
3. se ricevuto, serializza `work_context` in `work-context.json`;
4. esegui localmente `.ai-evo-prj/scripts/acme-operation-output-worklog record`, passando quei percorsi alle rispettive opzioni, la directory a `--temporary-directory` e gli altri input alle opzioni omonime; se `artifact_name` è valorizzato, passalo come `--artifact-name` per salvare lo stesso output come artefatto stabile; aggiungi `--complete` solo quando `complete` è `true`;
5. lascia al logger la rimozione dei file temporanei e restituisci il suo stdout invariato.

Non interpretare l'output, non rieseguire il comando sorgente e non modificare codice o Git.

Gli input richiesti sono `session_name`, `recipe_name`, `session_input`, `step_name`, `source_name`, `outcome`, `output`, `error` e `complete`. `work_context` è opzionale; fuori da iterazioni omettere `--work-context`.

## Expected output

Stdout invariato del logger e checkpoint nella sessione .ai-evo-work.

## Constraints

Non interpretare l’output né rieseguire il comando sorgente; non modificare codice o Git.

## Success criteria

Il checkpoint conserva input, output ed esito ricevuti e il logger termina senza errori.

## Examples

```text
$acme-cmd-save-worklog-output
```
