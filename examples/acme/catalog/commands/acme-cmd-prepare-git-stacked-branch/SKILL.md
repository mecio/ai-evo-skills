---
name: acme-cmd-prepare-git-stacked-branch
description: >-
  Materializza un singolo branch locale già definito da un manifest stacked approvato. Non genera nomi, modifica
  codice, crea commit o pubblica lo stack.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
  ai-evo-recipe-only: false
---

# Preparazione di un branch stacked pianificato

## Purpose

Creare un solo branch locale usando letteralmente nome, parent e posizione già stabiliti dal comando che ha
preparato il manifest dello stack.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
  capabilities: [acme.git-prepare-branch]
  deny-capabilities: [git.remote-write, github.remote-write]
inputs:
  work_specification:
    description: Specifica ready del work item con base, branch, parent e sequenza approvati.
    required: true
```

## Procedure

1. Con un handoff risolto eseguire direttamente dal passaggio 2; altrimenti pianificare il comando e applicare
   modalità, policy, input e profilo ricevuti.
2. Richiedere una specifica ready e ricavarne letteralmente `base_branch`, `parent_branch`, `branch` e
   `sequence`. Non generare o normalizzare i nomi e non installare `gh stack`.
3. Dalla root applicativa eseguire `.ai-evo-prj/scripts/acme-git-local prepare-branch '<JSON>'`, passando
   esattamente questi quattro campi in un solo argomento JSON quotato come dato, mai come codice shell.
   L'helper verifica nomi, base e parent locali, worktree pulita, branch corrente e assenza del nuovo branch.
   Per il primo layer esegue soltanto `gh stack init --base <base> <branch>`; per i successivi verifica
   lo stack del parent e chiama soltanto `gh stack add <branch>`.
4. L'helper richiede che il branch creato sia quello dichiarato e che l'OID iniziale coincida col parent.
   Propagare il primo errore e conservarne la diagnostica: non ripetere una scrittura senza verificarne
   gli eventuali effetti parziali. Non eseguire direttamente altri comandi Git o gh.
5. Restituire esclusivamente il nome completo del branch prodotto dall'helper. Nessun push, submit o sync.

## Expected output

Il solo nome completo del branch creato, utilizzabile direttamente dagli step successivi.

## Constraints

- Creare esclusivamente un branch locale per invocazione.
- Usare soltanto i valori già presenti nel manifest approvato.
- Richiedere una worktree pulita e non modificare base o parent.
- Non eseguire alcuna operazione remota.

## Success criteria

- `HEAD` è sul branch restituito e il suo OID iniziale coincide con il parent dichiarato.

## Examples

```text
$acme-cmd-prepare-git-stacked-branch work_specification="<ready con base, parent, branch e sequenza>"
```
