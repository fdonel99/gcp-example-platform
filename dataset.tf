# --- GESTIONE DATASET ---

# NORTHSTAR

resource "google_bigquery_dataset" "dataset_principale" {
  dataset_id                  = "NORTHSTAR" 
  friendly_name               = "Database Northstar"
  description                 = "Dataset principale per l'importazione e analisi dati"
  location                    = "EU"
  delete_contents_on_destroy = false 
}