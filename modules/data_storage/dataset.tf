# --- GESTIONE DATASET ---

resource "google_bigquery_dataset" "dataset_principale" {
  project                    = var.project_id
  dataset_id                 = "NORTHSTAR" 
  friendly_name              = "Database Northstar - ${title(var.environment)}"
  description                = "Dataset principale per l'importazione e analisi dati (${var.environment})"
  location                   = "EU"
  
  # TRUCCO: In produzione non vogliamo MAI cancellare i dati per sbaglio (false).
  # In test, invece, potremmo voler distruggere e ricreare l'ambiente senza errori (true).
  delete_contents_on_destroy = var.environment == "test" ? true : false 
}