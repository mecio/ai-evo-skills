---
name: acme-cmd-verify-impl
description: Verifica staticamente che un'implementazione corrisponda alla specifica affidata. Usare nella delega generica per controllare modifiche e scope; non produce né sostituisce evidenze di test.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Verifica dell'implementazione

## Purpose

Controllare il lavoro prodotto dall'esecutore rispetto all'handoff originario, confermando nel codice corrente
modifiche dichiarate, scope e criteri verificabili staticamente. Dichiarare separatamente i criteri che richiedono
test o esecuzione e che questo comando non può confermare.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  implementation_report:
    description: Rapporto prodotto da acme-cmd-implement-work, privo di risultati di test.
    required: true
  conversation_summary:
    description: Contesto aggiuntivo per invocazioni generiche; può essere vuoto con specifica autosufficiente.
    default: ""
  work_specification:
    description: Specifica operativa affidata all'esecutore.
    required: true
  acceptance_criteria:
    description: Criteri aggiuntivi; può essere vuoto quando sono inclusi nella specifica.
    default: ""
  constraints:
    description: Vincoli tecnici o operativi aggiuntivi.
    default: ""
```

## Procedure

1. Quando viene fornito un `ai-evo-execution-handoff`, usare input, policy e profilo già risolti ed eseguire
   direttamente il task descritto dai passaggi 5-9, senza richiamare planner o `command execute`.
2. Altrimenti eseguire `.ai-evo/bin/ai-evo-skills command plan acme-cmd-verify-impl`, indicando
   l'adapter corrente, tutti gli input ricevuti e l'eventuale `--ai-effort-profile`.
3. Fermarsi se pianificazione o validazione falliscono.
4. Applicare directory di lavoro, modalità, argomenti CLI, `prompt_delivery`, `policy_instructions` e istruzioni
   del profilo restituiti. In modalità `delegated`, inviare il piano risolto completo tramite standard input a
   `.ai-evo/bin/ai-evo-skills command execute` e restituirne l'output; in modalità `current`, proseguire.
5. Leggere `entrypoint.md`, le direttive pertinenti e lo stato Git. Esaminare in modo mirato i file e il diff
   citati da `implementation_report`, preservando e distinguendo le modifiche preesistenti quando identificabili.
6. Confrontare ogni elemento di `work_specification` e ogni criterio verificabile staticamente con codice,
   configurazione, documentazione e test presenti. Non considerare sufficiente una dichiarazione del rapporto
   quando può essere verificata direttamente nella worktree.
7. Classificare esplicitamente come `execution-required` i criteri che dipendono dall'esecuzione di test, lint,
   build o servizi. Non eseguire questi controlli, non cercarne l'esito nel rapporto di implementazione e non
   trasformare la loro assenza in un successo.
8. Classificare il risultato come `implementation-consistent`, `correction-required` oppure
   `user-decision-required`. Per ogni
   scostamento indicare priorità, file e righe, criterio violato, impatto e correzione consigliata. Per una
   decisione funzionale presentare alternative, conseguenze e raccomandazione.
9. Restituire un rapporto finale autosufficiente con classificazione, criteri verificati staticamente, criteri
   `execution-required`, findings e rischi residui. Non modificare la worktree.

## Expected output

Un rapporto Markdown che collega il risultato alle specifiche, conferma o contesta le modifiche dichiarate e
distingue i criteri verificati staticamente da quelli `execution-required`.

## Constraints

- Operare in sola lettura.
- Non accettare come prova una sola affermazione non verificabile del rapporto precedente.
- Non attribuire all'esecutore modifiche preesistenti senza evidenze.
- Non ripetere test superati se il codice e l'ambiente non sono cambiati.
- Non correggere direttamente gli scostamenti rilevati.

## Success criteria

- Ogni criterio è confermato staticamente, contestato oppure classificato `execution-required` con motivazione.
- I findings contengono riferimenti puntuali al codice corrente.
- Il risultato distingue fatti osservati, dichiarazioni del rapporto e decisioni funzionali.
- La worktree non viene modificata.

## Examples

```text
$acme-cmd-verify-impl implementation_report="..." work_specification="..."
```
