# Struttura Logica del Progetto

*Ultimo aggiornamento automatico: 18/08/2026 alle 12:46:57 (UTC) (Deploy in ambiente: **test**)*

---

# Struttura logica e organizzazione delle directory del progetto

Questo documento descrive la struttura e l'organizzazione delle directory del progetto, fornendo una panoramica della sua architettura e dei componenti utilizzati. La struttura è progettata per garantire chiarezza, mantenibilità e facilità di navigazione.

## Struttura delle Directory

```
./
    ├── map.drawio
    ├── gha-creds-70ca5ac3dd18526c.json
    ├── modules/
    │   ├── data_storage/
    │   │   ├── merge_storico.txt
    │   │   ├── variables.tf
    │   │   ├── dataset.tf
    │   │   ├── outputs.tf
    │   │   └── storage.tf
    │   ├── orchestration/
    │   │   ├── variables.tf
    │   │   └── scheduler.tf
    │   ├── compute_functions/
    │   │   ├── cloud_function_traduzione_infografiche.tf
    │   │   ├── cloud_function_calcolo_spese_trasporto.tf
    │   │   ├── variables.tf
    │   │   ├── cloud_function_anagrafica_prodotto.tf
    │   │   ├── outputs.tf
    │   │   ├── cloud_function_load_storico.tf
    │   │   ├── cloud_function_estrazione_spese_trasporto.tf
    │   │   ├── cloud_function_report_fornitori.tf
    │   │   ├── cloud_function_drive_to_gcp.tf
    │   │   ├── cloud_function_report_giacenze.tf
    │   │   ├── cloud_function_load_tabelle.tf
    │   │   ├── src/
    │   │   │   ├── estrazione_spese_trasporto.zip
    │   │   │   ├── traduzione_infografiche.zip
    │   │   │   ├── drive_to_gcp.zip
    │   │   │   ├── load_storico.zip
    │   │   │   ├── report_fornitori.zip
    │   │   │   ├── tables_loading.zip
    │   │   │   ├── anagrafica_prodotto.zip
    │   │   │   ├── calcolo_spese_trasporto.zip
    │   │   │   ├── report_giacenze.zip
    │   │   │   └── tables_loading/
    │   │   │       ├── main.py
    │   │   │       ├── primary_keys.json
    │   │   │       └── requirements.txt
    │   │   └── [altre cartelle di funzioni]
    │   │       ├── main.py
    │   │       └── requirements.txt
    │   └── setup/
    │       ├── secrets.tf
    │       ├── sa.tf
    │       ├── variables.tf
    │       ├── api.tf
    │       ├── outputs.tf
    │       ├── policy.tf
    │       └── accounts.tf
    ├── bootstrap/
    │   ├── prod/
    │   │   └── main.tf
    │   └── test/
    │       └── main.tf
    └── environments/
        ├── prod/
        │   ├── main.tf
        │   ├── variables.tf
        │   └── backend.tf
        └── test/
            ├── main.tf
            ├── variables.tf
            └── backend.tf
```

## Descrizione delle Directory e dei File

### Root Directory

- **`map.drawio`**: File di diagramma che rappresenta visivamente la struttura e i flussi del progetto.
- **`gha-creds-70ca5ac3dd18526c.json`**: File contenente le credenziali per l'accesso a Google API, probabilmente utilizzato per gestire le autorizzazioni in relazione a Google Cloud.

### Directory `modules/`

Questa directory ospita varie sottocartelle per componenti modulari del progetto.

- **`data_storage/`**: Contiene file relativi alla gestione dello storage dei dati, in particolare per la fusione e gestione di dati storici.
  - **File**: `variables.tf`, `dataset.tf`, `outputs.tf`, `storage.tf` per gestire le risorse di storage.
  
- **`orchestration/`**: Contiene configurazioni per la pianificazione e orchestrazione delle varie funzioni.
  - **File**: `variables.tf`, `scheduler.tf` per definire variabili e gestire la pianificazione delle attività.
  
- **`compute_functions/`**: Directory dedicata alle funzioni di calcolo, ognuna sembra gestire operazioni diverse come traduzioni, estrazioni e rapporti.
  - **File**: Varie configurazioni per ciascuna funzione (es. `cloud_function_traduzione_infografiche.tf`) e `src/`, che contiene gli script sorgente e le dipendenze necessarie per ciascuna funzione.
  
- **`setup/`**: Contiene file necessari per impostare e configurare l'ambiente, comprese le risorse necessarie (es. Service Account, permessi).
  - **File**: `secrets.tf`, `sa.tf`, `api.tf`, `policy.tf`, ecc. 

### Directory `bootstrap/`

Questa directory contiene i file di bootstrap per i diversi ambienti.

- **`prod/`** e **`test/`**: Directory dedicate alla configurazione di base dell'infrastruttura per gli ambienti di produzione e test, rispettivamente. Ognuna contiene un file `main.tf` per la definizione delle risorse.

### Directory `environments/`

Organizza le configurazioni per i vari ambienti.

- **`prod/`** e **`test/`**: Contengono i file necessari per definire le risorse specifiche per ciascun ambiente, come variabili e backend per lo stato dell'infrastruttura.
  - **File**: `main.tf`, `variables.tf`, `backend.tf` per gestire le risorse e le configurazioni specifiche per la produzione e il test.

## Conclusione

Questa struttura organizza il progetto in maniera logica, separando chiaramente le diverse responsabilità. Ogni directory ha uno scopo specifico e aiuta a mantenere il codice modulare e facile da gestire. Utilizzando questa architettura, è possibile garantire una chiara separazione delle preoccupazioni, facilitando sia lo sviluppo che il mantenimento del progetto nel tempo.