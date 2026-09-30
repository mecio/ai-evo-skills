# Recipe per issue GitHub

Ogni recipe svolge una fase circoscritta e salva il risultato nel percorso relativo `.ai-evo-work/<worklog_session_name>/`. Lo sviluppatore legge l’artefatto conclusivo e sceglie la recipe successiva.

## Flusso

| Fase | Recipe | Quando usarla |
|---:|---|---|
| 00 | `acme-recipe-00-design-github-issue` | Descrivere un problema e creare una nuova issue approvata. |
| 01 | `acme-recipe-01-refine-github-issue` | Opzionale: migliorare una issue già esistente o appena creata. |
| 02 | `acme-recipe-02-analyze-github-issue-code` | Analizzare issue, direttive e codice. |
| 03 | `acme-recipe-03-breakdown-github-issue` | Decidere se l’issue resta unitaria, diventa epic o usa layer stacked. |
| 04 | `acme-recipe-04-implement-github-issue` | Implementare una issue esecutiva e pubblicarne subito il branch stacked. |
| 04 | `acme-recipe-04-implement-github-issue-correction` | Correggere esplicitamente un checkpoint di implementazione non ancora pubblicato. |
| 05 | `acme-recipe-05-review-github-issue` | Revisionare il branch rispetto al parent dello stack. |
| 06 | `acme-recipe-06-verify-github-epic-stack` | Solo epic: verificare l’insieme delle sub-issue completate. |
| 07 | `acme-recipe-07-push-github-stack` | Su richiesta esplicita: ripubblicare e verificare lo stack completo dopo la review. |
| 08 | `acme-recipe-08-submit-github-stack` | Su richiesta esplicita: creare o aggiornare in draft le pull request dello stack. |

Un’issue non scomposta segue `00 → 02 → 03 → 04 → 05`; dopo il checkpoint `implement_issue` e prima del push può inserire una o più sessioni `04-correction`, poi prosegue con `05`. Una epic segue `00 → 02 → 03`, quindi `04 → 05` per ogni sub-issue nell’ordine delle dipendenze, e infine `06`; con autorizzazione esplicita può concludersi con `07 → 08`. Una issue `stacked` segue `00 → 02 → 03`, poi per ogni layer ordinato `adopt | (04 → 05, review persistita)` e può inserire `04-correction` nello stesso layer prima della pubblicazione.

## Attributi comuni

Tutte le recipe ricevono questi attributi:

| Attributo | Uso |
|---|---|
| `worklog_session_name` | Percorso relativo, umano e stabile della sessione sotto `.ai-evo-work/`. |
| `worklog_session_input` | Oggetto JSON immutabile con gli input della fase; rende riproducibile il recupero. |

Per le recipe dalla 01 alla 06, `recipe plan` esegue il resolver del workflow prima di validare gli input. La
recipe 04 pubblica obbligatoriamente il branch appena commitato e ne salva l'evidenza nel worklog, salvo la sessione
di correzione esplicitamente aperta da un checkpoint di implementazione non pubblicato. La recipe 07
non usa il resolver: la sua invocazione esplicita, con un report di verifica e `publication_authorized: "true"`,
autorizza la ripubblicazione finale dell'intero stack dopo la review.
Il blocco `input-resolver.with` passa anche il nome letterale della recipe pianificata: il runtime richiede infatti
che `recommended_recipe` coincida con quella recipe. Se non esiste alcuna sessione locale, la 01 e la 02 possono
quindi iniziare direttamente da una issue esistente: il resolver, senza accedere alla rete, restituisce
rispettivamente `issue-<numero>/attempt-01/01-refine-attempt-01` o
`issue-<numero>/attempt-01/02-analyze-attempt-01` e un `worklog_session_input` con `issue` e gli eventuali
`developer_instructions`. Le recipe dalla 03 alla 06 restano bloccate esplicitamente, perché richiedono artefatti
delle fasi precedenti. L'esistenza e lo stato aperto della issue sono verificati dallo step
`acme-cmd-analyze-github-issue`, che legge GitHub.

Dopo una recipe 00, la recipe 02 può ricevere `issue="pending"` e `issue_number="<numero creato>"`. Il resolver
verifica offline il checkpoint `create_issue` della sola sessione `issue-pending` che contiene quel numero, avvia
`issue-<numero>/attempt-01/02-analyze-attempt-01` e salva `creation_session` nel nuovo input immutabile. In questo
modo la cartella pending resta immutabile e la lineage verso l'issue reale è esplicita.
In ogni altro passaggio alla recipe 02, incluso dopo una 00 o 01 già registrata sotto l'issue reale, il resolver
fornisce comunque `issue_number` con il numero risolto: lo step di analisi non riceve mai un valore vuoto.

Con una sessione esistente, il resolver seleziona la recipe successiva, recupera gli artefatti e gli attributi
comuni disponibili e segnala soltanto gli input che restano necessari. Un input esplicito prevale su quello
risolto, che a sua volta prevale sul default della recipe. La recipe 00 resta esclusa perché l'issue non esiste
ancora.

Per una issue principale usare sempre il percorso canonico:

```text
issue-<numero|pending>/attempt-<nn>/<recipe>-<azione>-attempt-<nn>
```

Per una sub-issue nata dalla scomposizione dell'epic usare:

```text
issue-<epic>/attempt-<nn>/subissues/issue-<sub-issue>/<recipe>-<azione>-attempt-<nn>
```

Per un layer di una sola issue `stacked` usare:

```text
issue-<numero>/attempt-<nn>/layers/L<k>/04-implement-attempt-<nn>
issue-<numero>/attempt-<nn>/layers/L<k>/04-correction-attempt-<nn>
issue-<numero>/attempt-<nn>/layers/L<k>/05-review-attempt-<nn>
```

`<recipe>` è il numero a due cifre della recipe, `<azione>` è l'azione canonica della fase e ogni `<nn>` è un contatore a due cifre. Le azioni sono `design`, `refine`, `analyze`, `breakdown`, `implement`, `correction`, `review`, `verify-epic`, `push` e `submit`. L'attempt subito sotto la issue identifica il workflow dell'epic; l'attempt finale identifica la singola fase sotto quel workflow. Per la recipe 00 usa `pending` finché la creazione dell'issue non restituisce il numero.

Esempi:

```text
issue-pending/attempt-01/00-design-attempt-01
issue-12553/attempt-01/01-refine-attempt-01
issue-12553/attempt-01/02-analyze-attempt-01
issue-12553/attempt-01/subissues/issue-12554/02-analyze-attempt-01
issue-12553/attempt-02/02-analyze-attempt-01
```

`worklog_session_input` contiene gli input funzionali risolti della fase, compresi `issue` e gli eventuali vincoli dello sviluppatore. Una sub-issue aggiunge `epic_issue`, `epic_attempt`, `epic_analysis_session` e `breakdown_session`; un layer aggiunge `layer_id`, `layer_sequence`, `breakdown_session` e `analysis_session`, così la lineage è verificabile anche fuori dalla struttura delle cartelle. Non riusare una sessione conclusa per un nuovo tentativo con input diversi.

Il trunk dipende dal contesto della worktree risolto da `acme-worktree-context`, ad esempio `legacy` o `current`.
Il resolver usa quel trunk per L0 e per confrontare le implementazioni; uno
stack locale che dichiara un trunk diverso viene segnalato.

Le `developer_instructions` ricevute dalla recipe 04 sono parte della specifica immutabile dell'implementazione. La recipe 05 della stessa issue o layer le riceve come `implementation_instructions`: insieme al body del layer definiscono il perimetro autorizzato della review.

## Come riprendere una sessione

Prima identificare la fase conclusa leggendo `.ai-evo-work/<sessione>/context.md` e `session.json`. Il record con `complete: true` contiene l’output da passare alla fase successiva; per esempio l’analisi della fase 02 è anche salvata come `issue-<numero>-analysis.json`.

Se una fase è conclusa, non la si riesegue: si avvia la recipe successiva con un nuovo `worklog_session_name` e si passa l’artefatto conclusivo come input. Esempio: dopo `issue-12540/attempt-01/02-analyze-attempt-01`, avviare la fase 03 con la relativa analisi e una nuova sessione `issue-12540/attempt-01/03-breakdown-attempt-01`.

Quando cambia la scomposizione, la recipe 03 può invece aprire esplicitamente un nuovo workflow attempt: usare `new_workflow_attempt="true"` e un `reason` non vuoto. Per #12549, dopo `issue-12549/attempt-01/03-breakdown-attempt-01` in modalità `single`, il resolver riusa l'analisi 02 di attempt-01 e propone `issue-12549/attempt-02/03-breakdown-attempt-01`, dove registrare la nuova mappa `stacked`. Il nuovo attempt è ammesso soltanto se l'attempt corrente non ha sessioni attive o fallite e non ha già creato sub-issue di un'epic.

Se una fase non è conclusa o fallisce, controllare prima lo stato Git e gli effetti remoti già avvenuti. Quando il checkpoint o gli input immutabili registrano un branch pubblicato, invocare prima `acme-cmd-prepare-git-recipe-branch` con il numero della issue: il comando legge i checkpoint di pubblicazione, seleziona la checkout corretta, recupera o ricostruisce lo stack e aggiorna il branch solo con fast-forward. Non usare strumenti di sincronizzazione dello stack nel recupero. Riutilizzare lo stesso `worklog_session_name` solo con gli stessi input funzionali; se issue, base branch o vincoli cambiano, creare una nuova sessione e registrare il motivo nel nuovo `worklog_session_input`.

Le recipe che producono effetti persistenti registrano prima un checkpoint non conclusivo. Se uno step successivo fallisce e la sessione è `active`, il coordinatore registra, quando dispone dell'errore, un checkpoint con `outcome: failed` e `complete: false`, poi si ferma senza avanzare. Per riprendere, recuperare piano e journal runtime della stessa recipe oppure completare il checkpoint; non rieseguire automaticamente gli effetti già verificabili.

Eccezione esplicita per la fase 04: se la sessione `04-implement` è `active`, l'ultimo checkpoint riuscito è `implement_issue` e non esiste `publish_branch`, lo sviluppatore può invocare la recipe di correzione con `correction_instructions` non vuote. Il resolver apre una sessione sorella `04-correction-attempt-<nn>`, conserva `implementation_session`, branch, parent e output 04 nel suo input immutabile. La 04 originale resta `active` come evidenza del commit non pubblicato; il resolver considera la correzione conclusa l'ultima fase valida. Una correzione ancora `active` dopo `correct_implementation` può generare un'altra sessione di correzione. Il percorso non è disponibile dopo la pubblicazione o la review.

Il runtime AI Evo può inoltre recuperare un prefisso di step già verificato soltanto se conserva il piano e il journal runtime originali. Usare `recipe recover` con nuove evidenze di dipendenze immutate; il recupero non ricrea automaticamente issue, branch, commit o file di worklog. Per un errore di un comando Codex, l’eventuale sessione nativa può essere ripresa solo se il piano dichiara il riuso della sessione; Claude non supporta al momento questa ripresa tramite `command execute`.

## Attributi per issue

| Attributo | Formato | Quando serve |
|---|---|---|
| `issue` | Numero (`"12541"`) o URL GitHub | Recipe 01, 02, 04 e 05. |
| `problem_description` | Testo libero | Recipe 00. |
| `developer_instructions` | Testo libero | Vincoli ulteriori per revisione, analisi o implementazione (recipe 01, 02 e 04). |
| `base_branch` | Nome branch Git | Recipe 04; prevale sulla base eventualmente proposta nell’issue. |
| `correction_instructions` | Testo libero non vuoto | Recipe 04 di correzione; delimita le sole modifiche aggiuntive autorizzate. |
| `layer` | JSON con `id`, `sequence`, `title`, `body`, `dependencies` | Recipe 04 per una issue `stacked`; limita l'implementazione al layer. |
| `base` | Nome del parent stacked, opzionale | Recipe 05; se vuoto viene risolto il parent dello stack. |
| `branch` | Nome del branch pubblicato registrato dalla recipe precedente | Recipe 05; consente di recuperare lo stack prima della review. |
| `issue_analysis` | JSON prodotto dalla recipe 02 | Recipe 03. |
| `stack_layer` | JSON con `base_branch`, `parent_branch`, `branch`, `sequence` | Recipe 05. |
| `epic_analysis` | JSON della recipe 02 sull’issue principale | Recipe 06. |
| `epic_breakdown` | JSON della recipe 03 | Recipe 06. |
| `verification_evidence` | Report e record delle sub-issue | Recipe 06. |

## Esempi

### Issue non scomposta

```text
$acme-recipe-02-analyze-github-issue-code \
  issue="12540" \
  developer_instructions="Non modificare il comportamento pubblico." \
  worklog_session_name="issue-12540/attempt-01/02-analyze-attempt-01" \
  worklog_session_input='{"issue":"12540","developer_instructions":"Non modificare il comportamento pubblico."}'

$acme-recipe-04-implement-github-issue \
  issue="12540" \
  base_branch="main" \
  developer_instructions="" \
  worklog_session_name="issue-12540/attempt-01/04-implement-attempt-01" \
  worklog_session_input='{"issue":"12540","base_branch":"main","developer_instructions":""}'
```

### Correzione prima del push

```text
$acme-recipe-04-implement-github-issue-correction \
  issue="12589" \
  correction_instructions="Usare JsonDb per acceptPrivacy()/getCurrentUserPrivacy() e isolare soltanto l'accodamento in pushTreatsHit()." \
  worklog_session_name="issue-12589/attempt-01/04-correction-attempt-01" \
  worklog_session_input='<input risolto dal resolver>'
```

Il resolver completa `branch`, `parent_branch` e `implementation_report` dal checkpoint 04. La correzione non crea né inizializza layer Git, non riscrive commit e restituisce tutti i commit rispetto al parent; `publish_branch` resta l'unica scrittura remota della recipe.

### Epic e sub-issue

```text
$acme-recipe-03-breakdown-github-issue \
  issue_analysis='<analisi JSON della issue 12540>' \
  worklog_session_name="issue-12540/attempt-01/03-breakdown-attempt-01" \
  worklog_session_input='{"issue":"12540","analysis_session":"issue-12540/attempt-01/02-analyze-attempt-01"}'

$acme-recipe-04-implement-github-issue \
  issue="12541" \
  base_branch="main" \
  worklog_session_name="issue-12540/attempt-01/subissues/issue-12541/04-implement-attempt-01" \
  worklog_session_input='{"issue":"12541","epic_issue":"12540","epic_attempt":1,"breakdown_session":"issue-12540/attempt-01/03-breakdown-attempt-01","base_branch":"main"}'
```

La recipe 04 crea il branch stacked come conseguenza dell’implementazione. Nello stesso branch realizza pre-test, codice, test di consolidamento e tutti i commit logici necessari per l’issue; non esegue push o `gh stack submit`.

### Issue stacked per layer

```text
$acme-recipe-04-implement-github-issue \
  issue="12549" \
  base_branch="feature/0.0_#12549_example/00_countryresolution" \
  layer='{"id":"L1","sequence":1,"title":"GDPR","body":"...","dependencies":["L0"]}' \
  worklog_session_name="issue-12549/attempt-02/layers/L1/04-implement-attempt-01" \
  worklog_session_input='{"issue":"12549","layer_id":"L1","layer_sequence":1,"analysis_session":"issue-12549/attempt-02/02-analyze-attempt-01","breakdown_session":"issue-12549/attempt-02/03-breakdown-attempt-01","base_branch":"feature/0.0_#12549_example/00_countryresolution"}'
```

Per adottare un layer già esistente, per esempio `L0` di #12549 sul branch `.../00_countryresolution`, aprire `attempt-02` con la scomposizione `stacked` e usare la recipe di adozione proposta dal resolver. Serve una conferma esplicita dello sviluppatore; l'adozione verifica solo lo stato Git locale e registra il checkpoint 04 con `origin: "pre-existing"`.
