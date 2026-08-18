# Struttura Logica del Progetto

*Ultimo aggiornamento automatico: 18/08/2026 alle 12:38:56 (UTC) (Deploy in ambiente: **test**)*

---

# Analisi della Struttura Logica e dell'Organizzazione delle Directory del Progetto

Questo documento fornisce una panoramica della struttura logica e dell'organizzazione delle directory del progetto. La disposizione dei file e delle cartelle è fondamentale per garantire chiarezza, manutenibilità e facilità d'uso.

## Struttura della Directory del Progetto

```
./
    map.drawio
    gha-creds-4e1656810458092a.json
    modules/
        data_storage/
            merge_storico.txt
            variables.tf
            dataset.tf
            outputs.tf
            storage.tf
        orchestration/
            variables.tf
            scheduler.tf
        compute_functions/
            # vari file di funzione
            ...
            src/
                # funzioni e codici sorgente
                ...
        setup/
            # configurazione necessaria
            ...
    bootstrap/
        # configurazioni di avvio per vari ambienti
        ...
    environments/
        # configurazioni specifiche per ambiente
        ...
```

### Descrizione delle Directory

1. **Root Directory (`./`)**
   - **map.drawio**: Presumibilmente un diagramma di architettura o processo creato con Draw.io.
   - **gha-creds-4e1656810458092a.json**: File di credenziali JSON, probabilmente utilizzato per l'autenticazione in API o servizi cloud.

2. **modules/**: Questa directory contiene diversi moduli organizzati in sotto-directory. Ogni modulo sembra avere una specifica funzionalità o componente del sistema.

    - **data_storage/**: Contiene file relativi alla gestione e definizione delle risorse di storage, con file `*.tf` che sono logiche di definizione delle risorse in Terraform, e `merge_storico.txt`, presumibilmente usato per tracciare le modifiche o i merge di dati storici.

    - **orchestration/**: Gestisce le logiche di orchestrazione e schedulazione delle operazioni all'interno del progetto. Include file `variables.tf` e `scheduler.tf` per la configurazione e la pianificazione delle esecuzioni delle funzioni.

    - **compute_functions/**: Modulo per funzioni di calcolo, dove si trovano le definizioni delle Cloud Functions scritte in Terraform e anche i pacchetti sorgente zippati (`.zip`). La struttura `src/` all'interno di questo modulo contiene ulteriori directory per ogni specifica funzione con file `main.py` e `requirements.txt` necessari per la loro esecuzione.

    - **setup/**: Contiene la configurazione iniziale delle risorse cloud, inclusi credenziali, autorizzazioni, variabili e politiche di sicurezza. Utilizza file `*.tf` per definire queste risorse in Terraform.

3. **bootstrap/**: Directory responsabile della configurazione iniziale per diversi ambienti (prod e test). Ogni sotto-directory contiene file `main.tf` per definire e avviare le risorse necessarie per ciascun ambiente.

4. **environments/**: Contiene specifiche configurazioni per differenti ambienti (produzione e test). Ogni sotto-directory include file per definire variabili e backend per le configurazioni Terraform specifiche per l'ambiente.

## Considerazioni generali

- **Modularità**: La struttura del progetto è altamente modulare, facilitando la manutenibilità e la scalabilità. Ogni modulo ha una chiara responsabilità, suddivisa in diverse cartelle a seconda della loro funzionalità.

- **Separazione delle preoccupazioni**: I file sono organizzati in modo da separare chiaramente la logica di storage dalla logica di orchestrazione e dalle funzioni di calcolo.

- **Utilizzo di Terraform**: È evidente che il progetto utilizza Terraform per la definizione e la gestione dell'infrastruttura, come dimostrato dalla presenza di file `*.tf`.

- **Diritti di accesso e sicurezza**: I file all'interno della cartella `setup/` iniziano a toccare aspetti di sicurezza e credenziali, che sono fondamentali nel contesto di un progetto cloud.

Questa struttura rende il progetto ben organizzato e preparato per crescenti complessità nel tempo, facilitando l'aggiunta di nuove funzionalità e miglioramenti continui.