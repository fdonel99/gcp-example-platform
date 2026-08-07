# --- GESTIONE DATASET ---

resource "google_bigquery_dataset" "dataset_principale" {
  project                    = var.project_id
  dataset_id                 = "NORTHSTAR" 
  friendly_name              = "DM Northstar - ${title(var.environment)}"
  description                = "Dataset principale per l'importazione e analisi dati (${var.environment})"
  location                   = "EU"
  
  labels = {
    scopo = "dm-northstar-storage-fisico"
  }
  delete_contents_on_destroy = var.environment == "test" ? true : false 
}

resource "google_bigquery_dataset" "dataset_dati_storico" {
  project                    = var.project_id
  dataset_id                 = "NORTHSTAR_STORICO" 
  friendly_name              = "DM Northstar Storico - ${title(var.environment)}"
  description                = "Dataset con lo storico di dati passati (${var.environment})"
  location                   = "EU"
  
  labels = {
    scopo = "dm-northstar-storage-fisico"
  }
  delete_contents_on_destroy = var.environment == "test" ? true : false 
}