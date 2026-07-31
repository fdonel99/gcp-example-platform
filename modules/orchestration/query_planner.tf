# --- GESTIONE PIANIFICAZIONE QUERY ---

locals {
  name_suffix = title(var.environment)
}

# ANAGRAFICA PRODOTTI
resource "google_bigquery_data_transfer_config" "schedulazione_anagrafica_prodotti" {
  project                = var.project_id
  display_name           = "Query Anagrafica Prodotti - ${local.name_suffix}"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 17:15"
  
  service_account_name   = var.cloud_worker_sa_email 

  params = {
    query = templatefile("${path.module}/sql/anagrafica_prodotti.sql", {
      project_id  = var.project_id # AGGIUNTO: Fondamentale per i file .sql
      bucket_name = var.bucket_anagrafica_prodotti_name
    })
  }
}

# REPORT FORNITORI
resource "google_bigquery_data_transfer_config" "schedulazione_report_fornitori" {
  project                = var.project_id
  display_name           = "Export Report Fornitori - ${local.name_suffix}"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 17:25" 
  
  service_account_name   = var.cloud_worker_sa_email

  params = {
    query = templatefile("${path.module}/sql/report_fornitori.sql", {
      project_id  = var.project_id # AGGIUNTO: Fondamentale per i file .sql
      bucket_name = var.bucket_report_fornitori_name
    })
  }
}