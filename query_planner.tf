# --- GESTIONE PIANIFICAZIONE QUERY ---

# ANAGRAFICA PRODOTTI

resource "google_bigquery_data_transfer_config" "schedulazione_anagrafica_prodotti" {
  display_name           = "Query Anagrafica Prodotti"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 17:15"
  service_account_name   = google_service_account.cloud_worker.email

  params = {
    query = templatefile("${path.module}/sql/anagrafica_prodotti.sql", {
      bucket_name = google_storage_bucket.anagrafica_prodotti.name
    })
  }

  depends_on = [
    google_project_iam_member.cloud_worker_permissions,
    google_storage_bucket.anagrafica_prodotti
  ]
}

# REPORT FORNITORI

resource "google_bigquery_data_transfer_config" "schedulazione_report_fornitori" {
  display_name           = "Export Report Fornitori"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 17:25" 
  service_account_name   = google_service_account.cloud_worker.email

  params = {
    query = templatefile("${path.module}/sql/report_fornitori.sql", {
      bucket_name = google_storage_bucket.report_fornitori.name
    })
  }

  depends_on = [
    google_project_iam_member.cloud_worker_permissions,
    google_storage_bucket.report_fornitori
  ]
}