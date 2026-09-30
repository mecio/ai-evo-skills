---
name: acme-cmd-review
description: Esegue una code review in sola lettura. Usare per analizzare un target rispetto alla base risolta e produrre findings verificabili.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Review del codice

## Purpose

Eseguire una code review in sola lettura, limitata al target e alla base di confronto indicati, e restituire
findings verificabili.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  issue:
    description: Numero o URL della issue a cui limitare la review; se vuoto non applicare questo filtro.
    default: ""
  work_specification:
    description: Specifica ready opzionale; se presente fornisce parent e vincoli del layer.
    default: ""
  implementation_instructions:
    description: Istruzioni esplicite con cui l'implementazione è stata autorizzata.
    default: ""
  previous_review:
    description: Percorso della review precedente; se presente verificare esplicitamente la chiusura dei suoi finding aperti.
    default: ""
  target:
    description: Ambito da revisionare; current include commit del branch e modifiche locali rispetto alla base.
    default: "current"
  base:
    description: Base di confronto; se vuota usare il branch stacked immediatamente sottostante, altrimenti la normale base Git.
    default: ""
  focus:
    description: Ambito della review; general seleziona le direttive pertinenti, full-directives le considera tutte e security approfondisce la sicurezza.
    default: "general"
  constraints:
    description: Vincoli aggiuntivi forniti dallo sviluppatore.
    default: ""
```

## Procedure

1. Quando viene fornito un `ai-evo-execution-handoff`, usare input, policy e profilo già risolti ed eseguire
   direttamente il task descritto dai passaggi 5-9, senza richiamare planner, `command execute` o una seconda
   istanza dell'AI.
2. Altrimenti eseguire `.ai-evo/bin/ai-evo-skills command plan acme-cmd-review`, indicando l'adapter
   corrente, gli input ricevuti e l'eventuale `--ai-effort-profile`.
3. Fermarsi se pianificazione o validazione falliscono.
4. Applicare directory di lavoro, modalità, argomenti CLI, `prompt_delivery`, `policy_instructions` e istruzioni
   del profilo restituiti. In modalità `delegated`, inviare il piano risolto completo tramite standard input a
   `.ai-evo/bin/ai-evo-skills command execute` e restituirne l'output; in modalità `current`, proseguire.
5. Verificare lo stato Git nella directory risolta. Se la policy limita Bash, eseguire le letture Git soltanto
   tramite `.ai-evo/bin/ai-evo-git-read` e usare gli strumenti nativi di lettura e ricerca per i file.
6. Se `issue` è valorizzata, limitare la review al lavoro della issue indicata. Se `previous_review` è valorizzato,
   leggerlo e verificare esplicitamente che i finding aperti siano stati chiusi oppure riproporli con evidenze aggiornate.
   Se `work_specification` è valorizzata, richiedere stato ready e usare il parent e i vincoli dichiarati. Il perimetro autorizzato è l'unione della specifica e di `implementation_instructions`: gli interventi esplicitamente richiesti vanno elencati nella sezione "Interventi richiesti dallo sviluppatore" e verificati per correttezza e isolamento, senza segnalarli come fuori perimetro. Il lavoro non coperto da nessuno dei due resta un finding di perimetro. Applicare obiettivo, target, base, focus e vincoli ricevuti. Se la `base` è vuota,
   risolverla prima della review: per un branch stacked usare il branch immediatamente sottostante, identificato
   dalle informazioni di stack disponibili o dal più vicino branch di lavoro il cui tip sia un antenato stretto
   del tip revisionato; escludere il target, il suo remote-tracking omonimo e i ref sullo stesso commit. Usare la
   normale base di integrazione solo in assenza di un branch stacked sottostante e fermarsi se più basi restano
   plausibili. Con `general`, selezionare le
   direttive tramite l'entrypoint e la matrice; con `full-directives`, leggere tutte le direttive e applicare
   quelle compatibili con la worktree; con `security`, includere sempre `acme-database-e-sicurezza.md` e
   approfondire i rischi di sicurezza oltre alle direttive normalmente pertinenti. Non incollare file leggibili
   dalla worktree e non inventariare il repository.
   Interpretare `target=current` come l'insieme dei commit del branch e delle modifiche staged, non staged e dei
   file non tracciati pertinenti rispetto alla base risolta.
7. Produrre findings ordinati per priorità, con file e righe, verifiche eseguite e punti aperti. Non modificare
   il working tree.
8. Ampliare l'analisi soltanto per dipendenze concrete e non inventariare il repository.
9. Restituire il report finale secondo la politica di output del profilo, senza diff, file completi o log
   riusciti.

## Expected output

Un report Markdown che identifica target e base risolti, con sintesi, findings ordinati per priorità, evidenze
puntuali, test necessari, errori e punti aperti. Non includere diff, file completi o log riusciti.

## Constraints

- Operare in sola lettura sulla worktree.
- Ampliare la ricerca soltanto per dipendenze concrete.
- Conservare all'AI coordinatrice la responsabilità del risultato finale.

## Success criteria

- Il comando termina con exit code 0.
- Il report contiene findings verificabili oppure dichiara motivatamente che non ne sono stati trovati.
- La worktree non viene modificata.
- Tutte le direttive obbligatorie dell'effort profile sono rispettate.

## Examples

```text
/acme-cmd-review
```
