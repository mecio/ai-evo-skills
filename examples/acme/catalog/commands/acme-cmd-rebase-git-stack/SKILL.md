---
name: acme-cmd-rebase-git-stack
description: Simula oppure, con autorizzazione esplicita, ribasa e ripubblica uno stack quando il trunk remoto è avanzato.
metadata: { ai-evo-kind: command, ai-evo-version: "1.0", ai-evo-recipe-only: false }
---

# Rebase di uno stack Git pubblicato

## Purpose

Gestire in modo verificabile il caso `stack-rebase-required` causato dall'avanzamento del trunk. Il comando
supporta il rebase solo se non produce conflitti e conserva esattamente la sequenza dei `git patch-id --stable`.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.git-stack-rebase, git.remote-write]
  deny-capabilities: [github.remote-write]
inputs:
  issue: { required: true, description: "Issue proprietaria dello stack pubblicato." }
  publication_authorized: { default: "false", description: "Solo true autorizza il push atomico con lease e il successivo allineamento locale." }
```

## Procedure

Esegui `.ai-evo-prj/scripts/acme-rebase-git-stack rebase '<JSON>'` con `issue` e
`publication_authorized`. Il valore può essere booleano oppure la stringa letterale `"true"` o `"false"`.

Il comando aggiorna prima i remote-tracking ref dello stack e rilancia il report. Se il report non richiede il
rebase, restituisce il report invariato. Se la causa è un layer intermedio corretto, restituisce
`unsupported-rebase-case`: questo caso resta fuori perimetro.

Con `publication_authorized=false` crea una worktree temporanea staccata, simula il rebase a cascata e verifica
linearità, titoli e patch-id. Rimuove poi la worktree e restituisce `stack-rebase-simulated`; non sposta branch,
non modifica le worktree dello sviluppatore e non scrive ref remoti. Il fetch iniziale può aggiornare i
remote-tracking ref e la simulazione può creare oggetti Git non referenziati.

Con `publication_authorized=true`, dopo gli stessi controlli ricontrolla stato locale e ref remoti, quindi
esegue un unico `git push --atomic` con un lease per ogni layer. Solo dopo il push verificato porta avanti il
trunk locale con fast-forward e allinea i branch locali e le loro worktree. Il comando non crea merge commit,
non modifica pull request e non scrive nel worklog; la registrazione resta a
`acme-cmd-republish-rebased-git-stack`.

## Expected output

JSON valido rispetto a `references/output.schema.json`: report del workflow, simulazione, conflitto oppure
diagnostica bloccante. `core.commentChar` diverso da `;` compare in `warnings` e non viene modificato.

## Constraints

Il push richiede `publication_authorized` letteralmente true. Non usare `gh stack push`, `gh stack sync`,
submit, merge remoto o modifiche alle PR. Il solo merge ammesso è `git merge --ff-only` nella worktree pulita
del trunk, dopo il push autorizzato: deve risultare un fast-forward.

In caso di conflitto, patch-id differente, divergenza locale o lease fallito il comando si ferma. Se il push è
già stato accettato e l'allineamento locale fallisce, non tenta un rollback remoto: l'output riporta OID e
comandi di recupero da usare soltanto dopo una nuova verifica dello stato.

Il caso dei figli di un layer intermedio corretto resta manuale. Un'interruzione dopo il push e prima
dell'allineamento può lasciare ref locali sui vecchi OID. Gli OID previsti da una simulazione successiva possono
differire per la data del committer, pur conservando gli stessi patch-id. Il fast-forward del trunk può aggiornare
una worktree pulita distinta da quelle dello stack, soltanto dopo il push autorizzato.

## Success criteria

La simulazione non cambia branch, worktree o ref remoti. L'esecuzione autorizzata pubblica tutti i layer in modo
atomico, allinea trunk e branch locali e produce un report `stack-republish-required`.

## Examples

```text
$acme-cmd-rebase-git-stack issue="12724" publication_authorized="false"
$acme-cmd-rebase-git-stack issue="12724" publication_authorized="true"
```
