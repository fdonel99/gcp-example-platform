# --- CLOUD FUNCTIONS ---

# DRIVE TO GCP

data "archive_file" "zip_drive_to_gcp" {
  type        = "zip"
  source_dir  = "${path.module}/src/drive_to_gcp" 
  output_path = "${path.module}/src/drive_to_gcp.zip"
}

resource "google_storage_bucket_object" "upload_zip_drive_to_gcp" {
  name   = "drive_to_gcp_${data.archive_file.zip_drive_to_gcp.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_drive_to_gcp.output_path
}

resource "google_cloudfunctions2_function" "function_drive_to_gcp" {
  project     = var.project_id
  name        = "drive-to-gcp-fn-${var.environment}"
  location    = var.region 
  
  labels = {
    scopo = "fn-drive-to-gcp"
  }
  
  description = "Importa dati da Google Drive a GCP (${var.environment})"

  build_config {
    runtime     = "python311" 
    entry_point = "drive_to_gcp" 

    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
        object = google_storage_bucket_object.upload_zip_drive_to_gcp.name
      }
    }
  } 

  service_config {
    min_instance_count               = 0
    max_instance_count               = 5
    available_memory                 = "1G"
    available_cpu                    = "1"
    timeout_seconds                  = 300
    max_instance_request_concurrency = 80
    
    service_account_email            = var.cloud_worker_sa_email
    environment_variables = {GOOGLE_CLOUD_PROJECT = var.project_id}

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