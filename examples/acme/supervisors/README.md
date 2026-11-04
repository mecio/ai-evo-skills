# Supervisor del workflow issue

Il supervisor coordina il workflow di una issue applicando una policy dichiarativa ai campi strutturati prodotti
da `acme-cmd-report-github-issue-workflow`. Non interpreta `suggested_invocation`, non sostituisce la logica delle
recipe e non deduce autorizzazioni mancanti.

`config.yaml` contiene invarianti, stati e regole comuni. I file sotto `profiles/` descrivono invece il target,
gli effetti ammessi e il comportamento da applicare a ciascuna recipe. La policy specifica della recipe prevale
sul blocco `default`, ma non può ampliare gli effetti ammessi dalla configurazione generale.

Il profilo iniziale `supervised-local` porta la issue fino a implementazione verificata, commit locale e worktree
pulita. Esegue la recipe 04 con `publish_branch: "false"` e termina prima delle recipe 07 e 08. Ogni esecuzione
acquisisce un'assegnazione esclusiva per issue, procede in modalità run-to-pause e conserva
il riepilogo conclusivo sotto `.ai-evo-work/issue-<n>/supervisor/runs/run-<nnn>/`.
Il boilerplate non impone resoconti o publisher specifici del progetto. Dopo un esito conclusivo, un progetto può
collegare un publisher accessorio secondo il contratto descritto in `../post-workflow-publishers.md`; il suo eventuale
fallimento non cambia l'esito già verificato del workflow.

Il profilo `supervised-draft-prs`, quando selezionato esplicitamente, abilita i push delle recipe 04, pubblica lo
stack verificato con la recipe 07 e crea o aggiorna le stacked PR in draft con la recipe 08. La selezione esplicita
del profilo autorizza `publication_authorized` e `submit_authorized`; restano vietati force push, conversione
ready-for-review, merge e ogni effetto remoto non dichiarato. Dopo la verifica delle PR draft il supervisor si
ferma con outcome `completed-draft-prs`.

L'assegnazione corrente è dichiarata in `.ai-evo-work/issue-<n>/supervisor/state.json`; i dettagli immutabili e
la storia sono sotto `runs/run-<nnn>/assignment.json`. Non esiste scadenza automatica: un supervisor deve
rilasciare esplicitamente l'assegnazione prima di restituire il controllo. Dopo un crash, un operatore porta
manualmente l'assegnazione da `active` a `interrupted`; soltanto allora un'altra AI, anche su un PC diverso, può
creare il run successivo. Ogni ripresa crea sempre un nuovo `run-<nnn>`, anche quando il nome dell'AI coincide.

Recupero manuale dopo un crash:

```text
acme-supervisor-github-issue-workflow interrupt --issue 1234 --assignment-id run-001 \
  --interrupted-by mario --reason "Crash del PC durante la recipe 04"
```

Su PC differenti la directory `.ai-evo-work/issue-<n>` deve essere trasferita o condivisa integralmente prima
della ripresa; due copie locali non sincronizzate non possono garantire un lock distribuito.

Avvio previsto:

```text
$acme-cmd-supervise-github-issue-workflow issue="1234" profile="supervised-local"
$acme-cmd-supervise-github-issue-workflow issue="1234" profile="supervised-draft-prs"
```
