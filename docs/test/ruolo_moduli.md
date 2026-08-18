# Ruolo dei Moduli e Logica Funzioni

*Ultimo aggiornamento automatico: 18/08/2026 alle 12:47:25 (UTC) (Deploy in ambiente: **test**)*

---

# Documento Operativo: Gestione delle Risorse Cloud con Terraform e Cloud Functions

## Moduli Terraform

### Modulo: `data_storage`
- **Scopo di Business**: Questo modulo è responsabile della creazione e gestione del data storage nel contesto del progetto. Impegna la gestione di dataset BigQuery e bucket di Cloud Storage, elementi chiave per le operazioni di data processing e storage fisico.
- **Risorse Create**:
  - Tre dataset BigQuery (`NORTHSTAR`, `NORTHSTAR_STORICO`, `NORTHSTAR_STAGING`) per immagazzinare e gestire sia i dati di produzione che quelli storici e di staging.
  - Diversi bucket di Google Cloud Storage per gestire archiviazioni specifiche, tra cui `import_ns_zip`, `spese_trasporto`, `infografica_input`, `infografica_output`, etc., ciascuno con regole di lifecycle configurate per la manutenzione e la pulizia automatica dei dati, specialmente per ambienti di test.

### Modulo: `orchestration`
- **Scopo di Business**: Gestisce la pianificazione automatizzata delle operazioni compute, orchestrando i jobs che attivano le Cloud Functions seguendo una cadenza temporale definita.
- **Risorse Create**:
  - Google Cloud Scheduler Jobs che automatizzano processi quali la traduzione di dati da Google Drive a BigQuery, il caricamento di tabelle in BigQuery, e l'esportazione di vari report su Google Sheets.

### Modulo: `compute_functions`
- **Scopo di Business**: Configura e distribuisce funzioni serverless (Cloud Functions) che eseguono operazioni di calcolo e trasformazione dati.
- **Risorse Create**:
  - Funzioni Cloud distribuite in diverse aree quali traduzione di infografiche, calcolo spese di trasporto, esportazione di anagrafica prodotti, caricamento file storici, tra altre operazioni specifiche del dominio aziendale.

### Modulo: `setup`
- **Scopo di Business**: Inizializzazione del project GCP, gestione delle API necessarie e configurazione dei Service Account con i ruoli appropriati per il funzionamento sicuro dei moduli e delle risorse sopra descritte.
- **Risorse Create**:
  - Service Accounts specifici per l'esecuzione di funzioni, scheduler e query con i relativi ruoli IAM.
  - Configurazioni secret manager per gestire in sicurezza i token e le credenziali utilizzate all'interno delle Cloud Functions.

## Cloud Functions

### Funzione: `tables_loading`
- **Logica Applicativa**: Questa funzione elabora i file SQLite caricati su Google Cloud Storage, estrae i dati e li trasforma, arricchendoli se necessario con ulteriori informazioni (come classificazioni aggiuntive) prima di caricarli su BigQuery. Gestisce sia le operazioni di staging che il delta merge sulle tabelle BigQuery target.
- **Funzionalità**: Estrazione e trasformazione dati, notifica tramite Telegram in caso di errori, e utilizzo di librerie Python avanzate come `polars` per la gestione efficiente delle operazioni sui dataframe.

### Funzione: `report_fornitori`
- **Logica Applicativa**: Genera un report aggirando dati provenienti da BigQuery. Questi dati vengono elaborati e sincronizzati in un Google Sheet dedicato, permettendo così la visualizzazione e gestione analitica su base continuativa.
- **Funzionalità**: Creazione automatica della tabella su BigQuery e popolarla con dati aggregati, manipolando informazioni ottenute da diverse tabelle per creare un report fornitori dettagliato in Google Sheets.

### Funzione: `traduzione_infografiche`
- **Logica Applicativa**: Utilizza l'OCR per estrarre il testo da infografiche, esegue una traduzione e formatta i testi tradotti con le rispettive cromie e allineamenti originali prima di salvare versioni multilingua delle infografiche su Cloud Storage.
- **Funzionalità**: Analisi delle immagini, traduzione multi-lingua tramite servizi IA, e gestione di overlay grafici per mantenere il layout visivo originale.

### Funzione: `drive_to_gcp`
- **Logica Applicativa**: Automatizza l'estrazione e il caricamento di file da una cartella Google Drive a un Google Cloud Storage bucket. Si occupa di elaborare solo i file più recenti, garantendo che i dati caricati siano sempre aggiornati.
- **Funzionalità**: Gestione delle eccezioni durante i trasferimenti di file e notifiche push via Telegram per errori o successi rilevanti.

### Funzione: `anagrafica_prodotto`
- **Logica Applicativa**: Compila e trasporta informazioni sui prodotti dall'ambiente BigQuery a Google Sheets. Questo processo è essenziale per tenere un inventario aggiornato delle specifiche dei prodotti.
- **Funzionalità**: Estrazione dati da BigQuery, formattazione e popolamento di fogli elettronici con sicurezza fornita attraverso integrazioni con Google Drive APIs.

Ciascuna Cloud Function è progettata per eseguire task specifici nel contesto delle operazioni della piattaforma cloud configurata. Viene data attenzione all'integrazione efficiente delle risorse cloud esistenti, l'automatizzazione dei task e il mantenimento di standard elevati di sicurezza e ottimizzazione delle performance.