---
name: acme-cmd-supervise-github-issue-workflow
description: Coordina una issue fino al target del profilo applicando report, recipe, assegnazione esclusiva e checkpoint persistenti.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Supervisione di un workflow issue

## Purpose

Sostituire lo sviluppatore nel ciclo report, decisione, recipe e verifica fino a una conclusione locale oppure a
un punto di attesa esplicito e recuperabile.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.workflow-report, acme.workflow-supervisor-claim, acme.workflow-supervisor-release, acme.workflow-supervisor-decide, acme.workflow-supervisor-record, acme.workflow-summary]
inputs:
  issue: { required: true, description: "Numero della issue da portare al target del profilo." }
  profile: { default: "supervised-local", description: "Profilo sotto skills/supervisors/profiles/; un profilo remoto deve essere selezionato esplicitamente." }
  owner: { default: "current-ai", description: "Nome dell'AI registrato nell'assegnazione; non identifica da solo una specifica esecuzione." }
  developer_instructions: { default: "", description: "Vincoli iniziali da passare al report e alle recipe." }
  input_overrides: { default: "{}", description: "Oggetto JSON con soli input richiesti in una precedente pausa." }
```

## Procedure

1. Leggi integralmente `.ai-evo-prj/skills/supervisors/README.md`, `config.yaml` e il profilo selezionato. Valida
   la policy con `acme-supervisor-github-issue-workflow validate`, poi acquisisci l'assegnazione con `claim`.
   Conserva l'`assignment_id` restituito e passalo a ogni successivo `record`, `release` e `summarize --record`.
   Se esiste qualsiasi assegnazione `active`, fermati senza modificare il workflow: anche la stessa AI in una
   ripresa successiva deve attendere il rilascio e creare un nuovo run.
2. Leggi `input_overrides` come oggetto JSON. Non accettare chiavi non elencate nel `missing_inputs` del report
   corrente. Non accettare mai `publication_authorized=true` o `submit_authorized=true` con un profilo che nega
   scritture remote. La selezione esplicita di `supervised-draft-prs` autorizza soltanto gli input remoti elencati
   nel relativo `remote_authorization`; il profilo predefinito resta `supervised-local`.
3. Fino a `runtime.max_transitions`, esegui il report dalla root della checkout. Alla prima iterazione senza
   worklog passa la `start.requested_recipe` del profilo; passa sempre `developer_instructions` e il
   `start.workspace_mode`. Nelle iterazioni successive rileggi lo stato reale senza dedurlo dalla conversazione.
4. Salva il JSON del report in un file temporaneo privato e invoca `decide` con issue, profilo e path. Registra
   report e decisione con `record`; non analizzare `suggested_invocation`.
5. Per `execute-recipe`, verifica che l'assegnazione sia ancora attiva registrando la decisione, poi pianifica esclusivamente `decision.recipe` con
   `.ai-evo/bin/ai-evo-skills recipe plan <recipe> --adapter <adapter-corrente>` e passa gli input strutturati della
   decisione più gli override ammessi. Guida il piano con `recipe advance`, esegui soltanto lo step risolto e
   conserva gli output invariati. Applica gli effetti del profilo senza ampliarli: `supervised-local` imposta
   `publish_branch=false` e conclude prima delle recipe 07 e 08; `supervised-draft-prs` consente i push dichiarati,
   esegue le recipe 07 e 08 e non autorizza force push, ready-for-review, merge o altre scritture remote.
6. Dopo ogni recipe riuscita applica `outcomes.succeeded` della relativa policy. Con `reread-report` registra
   l'esito e torna al report. Con `evaluate-review`, leggi il checkpoint indicato da
   `result_handling.checkpoint_step`: se la review verificata non contiene finding azionabili, torna al report;
   se contiene finding confermati, trasformali in istruzioni di correzione puntuali e rilancia il report
   richiedendo `acme-recipe-04-implement-github-issue-correction`, senza chiedere allo sviluppatore decisioni
   tecniche già risolte dalla review. Se il risultato è ambiguo o richiede una scelta di prodotto, applica
   `on_ambiguous_result` e passa il controllo. Dopo un fallimento registra diagnostica ed esito, rilascia l'assegnazione
   con una motivazione e restituisci `blocked`; non ripetere effetti né superare `max_attempts`.
7. Per `request-input` o `handoff`, registra lo stato, rilascia l'assegnazione e restituisci gli input mancanti,
   il motivo e `daily_activity: null`. Usa `daily_activity: null` anche per ogni altra uscita
   (`blocked`, `incomplete` o `policy-violation`). Una nuova invocazione riparte dal worklog e può ricevere i
   valori tramite `input_overrides`.
8. Per `finalize`, invoca `summarize --record` con issue, profilo, owner e `assignment_id` e usa il riepilogo come
   unica fonte del messaggio conclusivo. Il boilerplate non impone publisher giornalieri di progetto: restituisci
   sempre `daily_activity: null`; un progetto può aggiungere un publisher accessorio idempotente senza cambiare
   l'esito del supervisor. Se l'esito non è uno dei due stati
   conclusivi, restituisci lo stato rilevato senza trasformarlo in successo. `summarize --record` conclude anche
   l'assegnazione.
9. Se si raggiunge `max_transitions`, registra e rilascia l'assegnazione, quindi restituisci `blocked` con motivo
   `transition-limit-reached`.

## Expected output

JSON conforme a [references/output.schema.json](references/output.schema.json). In caso di completamento include
integralmente il riepilogo prodotto dal comando di report; in pausa include gli input mancanti e le coordinate di
ripresa. Il campo di compatibilità `daily_activity` resta `null`: eventuali publisher sono estensioni di progetto.

## Constraints

- Non inferire autorizzazioni, decisioni o input mancanti.
- Non eseguire scritture remote negate dal profilo selezionato né effetti diversi da quelli delle recipe ammesse.
- Con `supervised-draft-prs`, fermarsi dopo avere verificato tutte le PR in stato draft.
- Non cambiare recipe rispetto alla decisione strutturata del profilo.
- Non mantenere un'assegnazione attiva quando restituisci il controllo allo sviluppatore.
- Non impostare autonomamente `interrupted`: è una transizione manuale riservata al recupero dopo un crash.

## Success criteria

Il supervisor termina con l'outcome dichiarato dal profilo e un consuntivo persistito, oppure con uno stato di
pausa che può essere ripreso senza memoria della conversazione.

## Examples

```text
$acme-cmd-supervise-github-issue-workflow issue="1234" profile="supervised-local"
$acme-cmd-supervise-github-issue-workflow issue="1234" profile="supervised-draft-prs"
```
