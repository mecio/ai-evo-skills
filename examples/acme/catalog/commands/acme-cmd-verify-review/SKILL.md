---
name: acme-cmd-verify-review
description: Verifica findings ed evidenze di una code review precedente. Usare per produrre una review finale controllata contro diff e codice corrente.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Verifica della review

## Purpose

Valutare criticamente una review precedente, scartare findings non sostenuti dal codice e produrre il rapporto
finale verificato.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  work_specification:
    description: Specifica ready opzionale; se presente fornisce il parent del layer verificato.
    default: ""
  implementation_instructions:
    description: Istruzioni esplicite con cui l'implementazione è stata autorizzata.
    default: ""
  review:
    description: Report completo prodotto dalla review precedente.
    required: true
  target:
    description: Ambito da revisionare; current include commit del branch e modifiche locali rispetto alla base.
    default: "current"
  base:
    description: Base di confronto; se vuota usare il branch stacked immediatamente sottostante, altrimenti la normale base Git.
    default: ""
  focus:
    description: Ambito della review; general seleziona le direttive pertinenti, full-directives le considera tutte e security approfondisce la sicurezza.
    default: "general"
```

## Procedure

1. Quando viene fornito un `ai-evo-execution-handoff`, usare input, policy e profilo già risolti ed eseguire
   direttamente il task descritto dai passaggi 5-10, senza richiamare planner o `command execute`.
2. Altrimenti eseguire `.ai-evo/bin/ai-evo-skills command plan acme-cmd-verify-review`, indicando
   l'adapter dell'AI corrente, gli input ricevuti e l'eventuale `--ai-effort-profile`.
3. Fermarsi se pianificazione o validazione falliscono.
4. Applicare directory di lavoro, modalità, argomenti CLI, `prompt_delivery`, `policy_instructions` e istruzioni
   del profilo restituiti. In modalità `delegated`, inviare il piano risolto completo tramite standard input a
   `.ai-evo/bin/ai-evo-skills command execute` e restituirne l'output; in modalità `current`, proseguire.
5. Se `work_specification` è valorizzata, richiedere stato ready e usare il parent dichiarato come base. Verificare il perimetro come unione di specifica e `implementation_instructions`: gli interventi esplicitamente richiesti sono riportati nella sezione "Interventi richiesti dallo sviluppatore" e non sono finding di perimetro, ma restano soggetti a verifica di correttezza e isolamento. Applicare le direttive secondo il focus: con `general`, selezionarle tramite l'entrypoint e la matrice; con
   `full-directives`, leggerle tutte e applicare quelle compatibili con la worktree; con `security`, includere
   sempre `acme-database-e-sicurezza.md` e approfondire i rischi di sicurezza oltre alle direttive normalmente
   pertinenti.
6. Se la `base` ricevuta è vuota, risolverla prima della verifica: per un branch stacked usare il branch
   immediatamente sottostante, identificato dalle informazioni di stack disponibili o dal più vicino branch di
   lavoro il cui tip sia un antenato stretto del tip revisionato; escludere il target, il suo remote-tracking
   omonimo e i ref sullo stesso commit. Usare la normale base di integrazione solo in assenza di un branch stacked
   sottostante e fermarsi se più basi restano plausibili. Verificare che coincida con la base dichiarata nel
   report precedente.
7. Interpretare `target=current` come l'insieme dei commit del branch e delle modifiche staged, non staged e dei
   file non tracciati pertinenti rispetto alla base risolta. Confrontare ogni finding con questo insieme e con il
   codice corrente.
8. Scartare le osservazioni non riproducibili o non sostenute da evidenze puntuali.
9. Eseguire soltanto i controlli richiesti dall'effort profile e dal rischio concreto.
10. Produrre la review finale senza modificare il working tree.

## Expected output

Una code review finale in Markdown che identifica target e base risolti, con findings confermati ordinati per
priorità, riferimenti a file e righe, verifiche eseguite e rischi residui.

## Constraints

- Non presentare come certo un finding non verificato.
- Non modificare il working tree.
- Non ripetere test superati quando codice e ambiente non sono cambiati.

## Success criteria

- Ogni finding pubblicato è stato confrontato con il codice corrente.
- Il risultato distingue verifiche completate, limiti e rischi residui.
- La worktree non viene modificata.
- Tutte le direttive obbligatorie dell'effort profile sono rispettate.

## Examples

```text
$acme-cmd-verify-review review="<report precedente>"
```
