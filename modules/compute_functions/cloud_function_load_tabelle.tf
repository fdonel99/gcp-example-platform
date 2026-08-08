# 1. Creazione del pacchetto ZIP dal codice sorgente
data "archive_file" "zip_tables_loading" {
  type        = "zip"
  source_dir  = "${path.module}/src/tables_loading" 
  output_path = "${path.module}/src/tables_loading.zip"
}

# 2. Caricamento dello ZIP sul bucket dedicato al codice delle funzioni
resource "google_storage_bucket_object" "upload_zip_tables_loading" {
  name   = "tables_loading_${data.archive_file.zip_tables_loading.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_tables_loading.output_path
}

# 3. Definizione della Cloud Function
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
    available_memory                 = "2Gi"
    available_cpu                    = "1"
    timeout_seconds                  = 3600
    max_instance_request_concurrency = 80
    service_account_email            = var.cloud_worker_sa_email
    
    # Variabili d'ambiente in chiaro
    environment_variables = {
      DATASET_ID  = "NORTHSTAR"
      STAGING_DATASET_ID = "NORTHSTAR_STAGING"
      BUCKET_NAME = var.bucket_import_ns_zip_name
      SHEET_ID    = "1ptH6m4mS6UozgrtRUfoP_wMMwbx7wTiIn1T6eJ0Vy1c" 
      GOOGLE_CLOUD_PROJECT = var.project_id
    }

    # Variabili d'ambiente SEGRETE (collegate a Secret Manager)
    secret_environment_variables {
      key        = "TELEGRAM_TOKEN"
      project_id = var.project_id
      secret     = var.telegram_secret_name 
      version    = "latest"
    }

    secret_environment_variables {
      key        = "TELEGRAM_CHAT_ID"
      project_id = var.project_id
      secret     = var.telegram_chat_id_secret_name 
      version    = "latest"
    }
  }
}

# 4. Montaggio del volume GCS Fuse per leggere lo ZIP grande
resource "null_resource" "mount_gcs_fuse_volume" {
  # Adesso lo script scatta se cambia la funzione, se cambia il nome del bucket o se cambia il codice ZIP!
  triggers = {
    function_id = google_cloudfunctions2_function.function_tables_loading.id
    bucket_name = var.bucket_import_ns_zip_name
    codice_hash = data.archive_file.zip_tables_loading.output_md5
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud run services update ${google_cloudfunctions2_function.function_tables_loading.name} \
        --project=${var.project_id} \
        --region=${google_cloudfunctions2_function.function_tables_loading.location} \
        --add-volume=name=bucket-zip,type=cloud-storage,bucket=${var.bucket_import_ns_zip_name} \
        --add-volume-mount=volume=bucket-zip,mount-path=/mnt/bucket \
        --execution-environment=gen2 \
        --quiet
    EOT
  }
}