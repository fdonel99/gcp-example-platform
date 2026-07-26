# --- CLOUD FUNCTIONS ---

#DRIVE TO GCP

data "archive_file" "zip_drive_to_gcp" {
  type        = "zip"
  source_dir  = "${path.module}/src/drive_to_gcp" 
  output_path = "${path.module}/src/drive_to_gcp.zip"
}

resource "google_storage_bucket_object" "upload_zip_drive_to_gcp" {
  name   = "drive_to_gcp_${data.archive_file.zip_drive_to_gcp.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_drive_to_gcp.output_path
}

resource "google_cloudfunctions2_function" "function_drive_to_gcp" {
  name        = "drive-to-gcp-fn"
  location    = "europe-west1" 
  description = "Importa dati da Google Drive a GCP"

  build_config {
    runtime     = "python311" 
    
    entry_point = "drive_to_gcp" 

    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
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
    service_account_email = google_service_account.cloud_worker.email
  }
}