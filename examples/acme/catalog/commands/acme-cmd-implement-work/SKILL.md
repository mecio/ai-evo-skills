---
name: acme-cmd-implement-work
description: >-
  Applica al codice una specifica già approvata per il progetto acme. Non crea o modifica test, non esegue
  suite e non crea commit.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Implementazione del lavoro

## Purpose

Realizzare la modifica prevista da una specifica autosufficiente dopo che i test di copertura sono stati creati.
Lasciare esecuzione delle suite, review, verifica e commit ai comandi successivi della recipe.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  conversation_summary:
    description: Contesto aggiuntivo per invocazioni generiche; può essere vuoto quando la specifica è autosufficiente.
    default: ""
  work_specification:
    description: Specifica concreta del lavoro da integrare o creare, con ambito, comportamento richiesto e limiti.
    required: true
  acceptance_criteria:
    description: Criteri aggiuntivi; può essere vuoto quando sono già inclusi nella specifica.
    default: ""
  constraints:
    description: Vincoli tecnici o operativi aggiuntivi.
    default: ""
  authorization:
    description: Vincoli operativi ulteriori; non autorizza commit o operazioni remote.
    default: ""
```

## Procedure

1. Quando viene fornito un `ai-evo-execution-handoff`, usare input, policy e profilo già risolti ed eseguire
   direttamente il task descritto dai passaggi 5-8, senza richiamare planner o `command execute`.
2. Altrimenti eseguire `.ai-evo/bin/ai-evo-skills command plan acme-cmd-implement-work`, indicando
   l'adapter dell'AI corrente, tutti gli input ricevuti e l'eventuale `--ai-effort-profile`.
3. Fermarsi se pianificazione o validazione falliscono.
4. Applicare directory di lavoro, modalità, argomenti CLI, `prompt_delivery`, `policy_instructions` e istruzioni
   del profilo restituiti. In modalità `delegated`, inviare il piano risolto completo tramite standard input a
   `.ai-evo/bin/ai-evo-skills command execute` e restituirne l'output; in modalità `current`, proseguire.
5. Verificare lo stato Git della worktree corrente prima di modificare file, leggere `entrypoint.md` e le
   direttive pertinenti, quindi confrontare l'handoff con il codice corrente. Preservare modifiche preesistenti
   e segnalare eventuali incompatibilità concrete tra specifica, repository e direttive.
6. Implementare tutto il codice applicativo necessario entro l'ambito autorizzato e aggiornare la documentazione
   direttamente coinvolta. Non creare o modificare test, inclusi quelli di copertura già prodotti; test di
   consolidamento, suite, review e verifica appartengono ai comandi successivi.
7. Non creare commit né pubblicare modifiche. La specifica può restringere l'operazione ma non ampliare il
   comando a versionamento o operazioni remote. Se emerge una scelta funzionale non risolvibile, lasciare
   la worktree in uno stato coerente e riportare opzioni, conseguenze e raccomandazione all'AI coordinatrice.
8. Restituire un rapporto conciso con modifiche effettuate, motivazione, file interessati, limiti e decisioni
   residue. Non dichiarare superati criteri o test che saranno controllati dai comandi successivi.

## Expected output

Una modifica applicativa completa nella worktree e un rapporto che collega ciascun file alla specifica, senza
file o risultati di test, review, verifica o commit.

## Constraints

- La specifica deve essere autosufficiente, selettiva e priva di dettagli estranei al lavoro.
- Le correzioni più recenti dello sviluppatore prevalgono sulle indicazioni precedenti incompatibili.
- L'esecutore non deve ampliare autonomamente l'obiettivo né riaprire decisioni già confermate.
- Le modifiche preesistenti nella worktree devono essere preservate.
- Operare esclusivamente nella worktree dalla quale è stato pianificato il comando; per lavorare altrove,
  invocare la recipe dalla worktree desiderata.
- Segreti, credenziali e contenuti non necessari non devono essere inclusi nell'handoff.
- L'AI coordinatrice conserva la responsabilità di verificare e comunicare il risultato finale.

## Success criteria

- L'esecutore riceve obiettivo, contesto, specifiche, criteri di accettazione, vincoli e autorizzazioni applicabili.
- L'implementazione rispetta le direttive pertinenti e non sovrascrive lavoro preesistente.
- Ogni modifica prevista è applicata oppure accompagnata da un limite concreto da verificare nel consolidamento.
- Le scelte non dimostrate vengono riportate con alternative e conseguenze invece di essere assunte.
- Il rapporto finale permette all'AI coordinatrice di controllare il lavoro senza ricostruire la conversazione.

## Examples

```text
/acme-cmd-implement-work work_specification="..."
```
