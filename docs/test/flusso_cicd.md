# Impostazione Flusso CI/CD

*Ultimo aggiornamento automatico: 18/08/2026 alle 12:39:19 (UTC) (Deploy in ambiente: **test**)*

---

# Analisi dei Workflow GitHub Actions CI/CD per Terraform

## Descrizione Generale

Il progetto utilizza GitHub Actions per eseguire flussi di lavoro CI/CD che deployano risorse su Google Cloud Platform (GCP) tramite Terraform. Ci sono due workflow distinti, uno per la produzione (`deploy-prod.yaml`) e uno per il test (`deploy-test.yaml`). Entrambi i workflow utilizzano le stesse fasi principali, ma sono configurati per operare su ambienti e rami diversi.

## Impostazione del Flusso CI/CD

### Workflow di Produzione (`deploy-prod.yaml`)

1. **Triggers**: Il workflow viene attivato da un evento `push` sul branch `main`. Le modifiche relative alla documentazione markdown (`.md`) vengono ignorate.
2. **Permessi**: È concesso il permesso di scrittura sui contenuti.
3. **Ambiente di Esecuzione**: Le azioni si eseguono su un runner Ubuntu (`runs-on: ubuntu-latest`).
4. **Variabili Ambientali**: Vengono definite variabili per il token Telegram utilizzando i segreti di GitHub.

Le fasi eseguite includono:

- Checkout del codice.
- Autenticazione in GCP.
- Configurazione e gestione di Terraform (Init, Plan, Apply).
- Setup di Python e installazione delle dipendenze.
- Esecuzione di uno script Python per la generazione della documentazione.
- Commit e push della documentazione generata.

### Workflow di Test (`deploy-test.yaml`)

1. **Triggers**: Il workflow viene attivato da un evento `push` sul branch `test`, ignorando anch'esso i file di documentazione markdown.
2. **Permessi e Ambiente di Esecuzione**: Come per il workflow di produzione.
3. **Variabili Ambientali**: Simili al workflow di produzione, tranne per le credenziali GCP che sono specifiche per l'ambiente di test.

Le fasi eseguite sono identiche a quelle del workflow di produzione con le stesse azioni principali riguardanti Terraform e la generazione della documentazione.

## Divisione degli Ambienti

- **Branch Main**: Utilizzato per la produzione. Qualsiasi modifica effettuata su questo branch attiva il workflow di produzione, il quale deploya direttamente le risorse in ambiente di produzione.
- **Branch Test**: Utilizzato per la fase di test. I push su questo branch attivano il workflow di test, dove si possono effettuare modifiche e verifiche prima di portare il codice in produzione.

## Eventi che Scatenano le Action

- **Push Events**: Entrambi i workflow sono progettati per attivarsi quando c'è un `push` sul branch specificato (main per produzione e test per testing). Questo assicura che ogni modifica nel codice venga immediatamente integrata nel processo CI/CD.

## Deploy Tramite Terraform

La sequenza delle azioni Terraform include:

1. **Terraform Init**: Inizializza il progetto Terraform, preparando il backend e il configuratore.
2. **Terraform Plan**: Crea un piano di esecuzione che mostra quali cambiamenti verranno apportati all'infrastruttura.
3. **Terraform Apply**: Applica il piano creato, effettuando i cambiamenti reali all'infrastruttura su GCP. L'opzione `-auto-approve` consente di eseguire il comando senza richiedere conferma manuale.

## Conclusione

Questo approccio ai flussi di lavoro GitHub Actions per Terraform fornisce una strategia chiara e robusta per la gestione di ambienti di produzione e test. La separazione tra i due workflow garantisce che il codice venga adeguatamente testato prima di essere distribuito in produzione, mentre l'automazione tramite Terraform semplifica la gestione delle infrastrutture nel cloud.