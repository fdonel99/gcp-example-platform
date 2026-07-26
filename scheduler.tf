# --- GESTIONE SCHEDULAZIONI CLOUD FUNCTIONS ---

# DRIVE TO GCP
resource "google_cloud_scheduler_job" "schedulazione_drive_to_gcp" {
  name             = "drive-to-bq-scheduler"
  description      = "Schedulazione per caricare i dati da Drive a BigQuery ogni domenica"
  schedule         = "45 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = "europe-west1"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.function_drive_to_gcp.service_config[0].uri
    oidc_token {
      service_account_email = google_service_account.cloud_worker.email
    }
  }

  depends_on = [
    google_cloudfunctions2_function.function_drive_to_gcp,
    google_project_service.api_necessarie
  ]
}

# TABLES LOADING

resource "google_cloud_scheduler_job" "schedulazione_tables_loading" {
  name             = "tables-loading-scheduler"
  description      = "Schedulazione per creare le tabelle in BigQuery ogni domenica"
  schedule         = "55 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = "europe-west1"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.function_tables_loading.service_config[0].uri
    oidc_token {
      service_account_email = google_service_account.cloud_worker.email
    }
  }

  depends_on = [
    google_cloudfunctions2_function.function_tables_loading,
    google_project_service.api_necessarie
  ]
}