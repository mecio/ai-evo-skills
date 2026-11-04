# Publisher successivi al workflow

Un progetto può eseguire un report, aggiornare un indice o avviare un'integrazione dopo che il workflow ha
raggiunto un esito verificato. Questo effetto è accessorio: non fa parte della transazione che determina l'esito
della recipe o del supervisor e un suo fallimento non può trasformare un workflow riuscito in fallito.

## Contratto consigliato

- Ricevere come input soltanto evidenze persistite: issue, outcome, path del riepilogo e identificatori Git o PR.
- Essere idempotente rispetto a una chiave stabile, per esempio `issue + workflow attempt + outcome`.
- Usare un lock limitato al singolo artefatto di destinazione, non il lock del supervisor o dell'intero worklog.
- Leggere lo stato corrente, costruire il nuovo contenuto fuori dal lock e verificare nuovamente la versione prima
  della scrittura; aggiornare file locali con sostituzione atomica.
- Registrare separatamente `created`, `updated`, `unchanged` o `pending`, senza modificare checkpoint e riepilogo
  immutabili del workflow primario.
- Rendere sicuro il retry: lo stesso input non deve duplicare righe, notifiche, deploy o altri effetti remoti.

Il coordinatore seriale decide quando invocare il publisher, ma non ne incorpora la logica. Ogni progetto dichiara
una capability dedicata e limita esplicitamente filesystem, rete ed effetti remoti. Operazioni irreversibili o con
impatto operativo, come un deploy, richiedono inoltre un'autorizzazione propria: il completamento del workflow non
la implica.

## Sequenza

1. Concludere e persistere il workflow primario.
2. Rilasciare l'assegnazione esclusiva del supervisor.
3. Invocare il publisher con riferimenti alle evidenze immutabili.
4. Registrare l'esito accessorio separatamente; in caso di errore lasciare uno stato `pending` recuperabile.

Questa separazione permette di aggiungere integrazioni specifiche senza rendere il catalogo `acme` dipendente da
formati di report, ambienti di deploy o servizi appartenenti a un singolo progetto.
