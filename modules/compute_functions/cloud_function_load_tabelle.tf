resource "google_cloudfunctions2_function" "function_tables_loading" {
  project     = var.project_id
  name        = "tables-loading-fn-${var.environment}"
  location    = var.region 
  labels = {
    scopo = "fn-caricamento-tabelle-in-bq"
  }
  description = "Carica i dati importati da Drive in tabelle Big Query (${var.environment})"

  build_config {
    runtime     = "python311" 
    entry_point = "run_sqlite_to_bigquery" 

    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
        object = google_storage_bucket_object.upload_zip_tables_loading.name
      }
    }
  }

  service_config {
    min_instance_count               = 0
    max_instance_count               = 3
    available_memory                 = "1Gi"
    available_cpu                    = "1"
    timeout_seconds                  = 3600
    max_instance_request_concurrency = 80
    service_account_email            = var.cloud_worker_sa_email
    
    # Variabili d'ambiente in chiaro
    environment_variables = {
      DATASET_ID  = "NORTHSTAR"
      BUCKET_NAME = var.bucket_export_ns_zip_name
      SHEET_ID    = "1ptH6m4mS6UozgrtRUfoP_wMMwbx7wTiIn1T6eJ0Vy1c" # Aggiunto!
    }

    # Variabili d'ambiente SEGRETE (collegate a Secret Manager)
    secret_environment_variables {
      key        = "TELEGRAM_TOKEN"
      project_id = var.project_id
      secret     = var.telegram_secret_name # <-- Richiama la variabile passata dal main
      version    = "latest"
    }

    secret_environment_variables {
      key        = "TELEGRAM_CHAT_ID"
      project_id = var.project_id
      secret     = var.telegram_chat_id_secret_name # <-- Richiama la variabile passata dal main
      version    = "latest"
    }
  }
}