# --- GESTIONE SCHEDULAZIONI CLOUD FUNCTIONS ---

# DRIVE TO GCP
resource "google_cloud_scheduler_job" "schedulazione_drive_to_gcp" {
  project          = var.project_id
  name             = "drive-to-bq-scheduler-${var.environment}"
  description      = "Schedulazione per caricare i dati da Drive a BigQuery ogni domenica (${var.environment})"
  schedule         = "45 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = var.function_drive_to_gcp_uri
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({
      folder_id   = var.drive_folder_id
      bucket_name = var.bucket_export_ns_zip_name
    }))
    oidc_token {
      service_account_email = var.cf_scheduler_sa_email
      audience              = var.function_drive_to_gcp_uri
    }
  }
}

# TABLES LOADING
resource "google_cloud_scheduler_job" "schedulazione_tables_loading" {
  project          = var.project_id
  name             = "tables-loading-scheduler-${var.environment}"
  description      = "Schedulazione per creare le tabelle in BigQuery ogni domenica (${var.environment})"
  schedule         = "55 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = var.function_tables_loading_uri
    oidc_token {
      service_account_email = var.cf_scheduler_sa_email
      audience              = var.function_tables_loading_uri
    }
  }
}

# TABLES LOADING
resource "google_cloud_scheduler_job" "schedulazione_tables_loading" {
  project          = var.project_id
  name             = "tables-loading-scheduler-${var.environment}"
  description      = "Schedulazione per creare le tabelle in BigQuery ogni domenica (${var.environment})"
  schedule         = "55 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = var.region

  http_target {
    http_method = "POST"
    uri         = var.function_tables_loading_uri
    oidc_token {
      service_account_email = var.cf_scheduler_sa_email
      audience              = var.function_tables_loading_uri
    }
  }
}