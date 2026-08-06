# --- GESTIONE PIANIFICAZIONE QUERY ---

locals {
  name_suffix = title(var.environment)
}

# REPORT FORNITORI
resource "google_bigquery_data_transfer_config" "schedulazione_report_fornitori" {
  project                = var.project_id
  display_name           = "Export Report Fornitori - ${local.name_suffix}"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 17:25" 
  
  service_account_name   = var.bq_scheduler_sa_email

  params = {
    query = templatefile("${path.module}/sql/report_fornitori.sql", {
      project_id  = var.project_id #
      bucket_name = var.bucket_report_fornitori_name
    })
  }
}