---
name: acme-cmd-report-github-issue-workflow
description: Individua il checkpoint più recente di una issue e consiglia la recipe successiva con gli input già risolti.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Ripresa del workflow di una issue GitHub

## Purpose

Riconoscere in quale fase si trova un workflow già avviato e produrre il solo prossimo passo eseguibile, senza
richiedere allo sviluppatore di ricordare nomi di recipe, sessioni o artefatti intermedi.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: disabled
  capabilities: [acme.workflow-report]
inputs:
  issue: { required: true, description: "Numero della issue, con o senza il prefisso #, oppure pending." }
  issue_number: { default: "", description: "Numero reale obbligatorio quando issue è pending." }
  requested_recipe: { required: true, description: "Recipe che il runtime sta pianificando." }
  developer_instructions: { default: "", description: "Vincoli iniziali dello sviluppatore da includere nel worklog del primo tentativo." }
  correction_instructions: { default: "", description: "Correzioni esplicite per una sessione 04 non ancora pubblicata." }
  new_workflow_attempt: { default: "", description: "\"true\" permette alla recipe 03 di aprire un nuovo attempt." }
  reason: { default: "", description: "Motivo obbligatorio quando new_workflow_attempt è true." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-report-github-issue-workflow report --issue '<issue>' --issue-number '<issue_number>' --requested-recipe '<requested_recipe>' --developer-instructions '<developer_instructions>' --correction-instructions '<correction_instructions>' --new-workflow-attempt '<new_workflow_attempt>' --reason '<reason>'` dalla root della worktree.
Restituisci invariato il JSON prodotto dallo script. Il comando seleziona il tentativo di workflow più recente,
legge soltanto i relativi checkpoint e artefatti e restituisce una recipe consigliata, la sessione da aprire,
gli input già determinabili e `suggested_invocation`, pronta da copiare.

Se non esiste ancora alcuna sessione locale, resta offline: non verifica GitHub. Per la recipe 01 o 02 restituisce
la recipe richiesta e gli input canonici di `issue-<numero>/attempt-01`; per le recipe 03-06 restituisce
`manual-assessment-required`, perché gli artefatti delle fasi precedenti non sono deducibili.

Per proseguire dopo la recipe 00 usare `issue: "pending"` e `issue_number: "<numero creato>"`. Il comando cerca
una sola recipe 00 completata sotto `issue-pending` il cui checkpoint `create_issue` contenga quel numero; se la
trova, prima di proporre la 01 o la 02 sposta atomicamente la sessione nel workflow canonico
`issue-<numero>/attempt-01/00-design-attempt-<nn>`. Normalizza i riferimenti interni, conserva `output` e
`output_sha256` del checkpoint e registra il nome precedente in `previous_session_name`; poi `creation_session`
nel nuovo input indica il percorso canonico. Se la sessione è già lì con lo stesso checkpoint il comando prosegue
senza duplicarla; se è ambigua, incompleta o la destinazione differisce, si ferma senza spostare nulla.

Per le sessioni spostate manualmente in passato, `migrate --issue '<numero>'` normalizza in modo esplicito e
idempotente `session_name`, `session_slug`, checkpoint e indice senza modificare gli output dei checkpoint.

Con `new_workflow_attempt: "true"` e recipe richiesta 03, richiede `reason`, riusa l'ultima analisi 02 conclusa
dell'attempt corrente e propone `attempt-<max+1>/03-breakdown-attempt-01`. Blocca l'operazione se esistono
sessioni da recuperare o se una scomposizione epic ha già creato sub-issue; non invalida effetti remoti.

Quando è richiesta la recipe di correzione 04, riconosce solo un checkpoint locale riuscito senza
`publish_branch`; restituisce una sessione `04-correction`, coordinate e output immutabile della 04. Le
`correction_instructions` esplicite restano l'unico input non deducibile.

Se `status` è `input-required`, chiedi soltanto i campi elencati in `missing_inputs`. Se è
`branch-recovery-required`, avvia `acme-recipe-resume-github-issue-workflow`: la recipe esegue il recupero e
rilancia il report. Se è `stack-rebase-required`, il branch è stato recuperato ma il trunk è avanzato: eseguire
manualmente rebase e push, poi rilanciare il report. Il nuovo stato `stack-republish-required` indica la recipe
che verifica i patch-id e registra i nuovi OID nel worklog prima di proseguire. Se è
`manual-assessment-required`, non inventare il passo successivo. Non avviare la recipe suggerita: il comando
orienta, mentre l'avvio resta una decisione esplicita dello sviluppatore.

## Expected output

Un JSON conforme a [references/output.schema.json](references/output.schema.json).

## Constraints

Non modifica Git o GitHub e non esegue recipe. `report` scrive solo nel worklog locale quando promuove una recipe
00 pending verificata; `migrate` scrive solo la metadata di una recipe 00 già spostata.

## Success criteria

Per un checkpoint concluso, lo sviluppatore ottiene una sola recipe successiva e i suoi input già risolti.

## Examples

```text
$acme-cmd-report-github-issue-workflow issue="12553" requested_recipe="acme-recipe-02-analyze-github-issue-code"

$acme-cmd-report-github-issue-workflow issue="pending" issue_number="12553" requested_recipe="acme-recipe-02-analyze-github-issue-code"
```
