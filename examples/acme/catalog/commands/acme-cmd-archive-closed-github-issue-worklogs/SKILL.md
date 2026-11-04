---
name: acme-cmd-archive-closed-github-issue-worklogs
description: Verifica su GitHub le issue con worklog locali e archivia le directory delle issue chiuse.
metadata: { ai-evo-kind: command, ai-evo-version: "1.0", ai-evo-recipe-only: false }
---

# Archiviazione dei worklog delle issue chiuse

## Purpose

Spostare sotto `.ai-evo-work/archive/` i worklog principali la cui issue GitHub è chiusa e non contiene attività
locali in corso, mantenendo consultabile la storia completa.

## Interface

```yaml ai-evo-interface
output-schema: references/output.schema.json
execution-policy:
  workspace: read-write
  network: enabled
  capabilities: [acme.github-issue-worklogs-archive]
inputs:
  dry_run: { default: "true", description: "Con true controlla e mostra il piano senza spostare directory; false applica l'archiviazione." }
```

## Procedure

Dalla checkout applicativa eseguire `.ai-evo-prj/scripts/acme-archive-closed-github-issue-worklogs archive`
passando un solo JSON con `dry_run`. L'helper considera esclusivamente le directory top-level canoniche
`.ai-evo-work/issue-<numero>`, legge con `gh` lo stato di ogni issue nello stesso repository e prepara tutti gli
spostamenti prima di modificare il worklog. Se la radice contiene sub-issue sotto uno o più
`attempt-*/subissues/issue-<numero>`, una issue principale chiusa è archiviabile soltanto quando anche tutte le
sub-issue distinte sono `CLOSED`. Con `dry_run: false`, sposta ogni radice archiviabile nel path
`.ai-evo-work/archive/issue-<numero>`; mantiene al proprio posto le issue principali aperte e le epic con almeno
una sub-issue aperta.

Le letture GitHub avvengono senza trattenere il lock globale del worklog e hanno un timeout di 20 secondi per
issue. Prima delle letture l'helper acquisisce uno snapshot dei path e dei metadati locali; subito prima degli
spostamenti acquisisce brevemente il lock condiviso e rifiuta l'operazione se lo snapshot non coincide più.
Se GitHub indica come chiusa una issue ma sessioni o supervisor locali risultano ancora `active`, l'helper mantiene
la radice al proprio posto con motivo `active-worklog` e riporta le coordinate in `local_blockers`. Non modifica
mai lo stato delle sessioni, dell'assegnazione o del run supervisor: tali attività devono essere concluse o
interrotte esplicitamente dal relativo proprietario prima di ripetere l'archiviazione.

Le radici `issue-pending*` e il contenuto già archiviato non vengono esaminati. Le sub-issue annidate vengono
controllate come condizione della radice epic e non vengono spostate separatamente. Se una lettura GitHub fallisce,
un path è un link simbolico o una destinazione esiste già, il
comando si ferma prima di spostare directory. Ogni rename è atomico; se uno spostamento successivo fallisce,
l'helper tenta il rollback di quelli già eseguiti.

## Expected output

Un JSON con stato `dry-run` oppure `archived`, conteggi complessivi e una voce per ogni issue principale con
stato GitHub, sub-issue verificate, eventuali sub-issue aperte, motivazione, azione, origine e destinazione.

## Constraints

- Non eliminare né modificare il contenuto dei worklog.
- Non modificare issue, branch, pull request o altri dati remoti.
- Non sovrascrivere una directory già presente nell'archivio.
- Non applicare gli spostamenti quando `dry_run` è omesso o vale `true`.
- Non archiviare worklog cambiati durante la verifica remota o con attività locali ancora attive.

## Success criteria

Tutte le issue top-level sono state verificate; in modalità applicativa quelle chiuse, senza sub-issue aperte né
attività locali in corso, sono sotto `archive`; le altre restano nella radice con una motivazione esplicita.

## Examples

```text
/acme-cmd-archive-closed-github-issue-worklogs dry_run="true"

/acme-cmd-archive-closed-github-issue-worklogs dry_run="false"
```
