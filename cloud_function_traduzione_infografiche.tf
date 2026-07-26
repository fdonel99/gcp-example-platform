# --- CLOUD FUNCTIONS ---

# TRADUZIONE INFOGRAFICHE 

data "archive_file" "zip_traduzione_infografiche" {
  type        = "zip"
  source_dir  = "${path.module}/src/traduzione_infografiche" 
  output_path = "${path.module}/src/traduzione_infografiche.zip"
}

resource "google_storage_bucket_object" "upload_zip_traduzione_infografiche" {
  name   = "traduzione_infografiche_${data.archive_file.zip_traduzione_infografiche.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_traduzione_infografiche.output_path
}

resource "google_cloudfunctions2_function" "function_traduzione_infografiche" {
  name        = "traduzione-infografiche-fn"
  location    = "europe-west1"
  description = "Trigger file input per la pipeline delle infografiche"
  
  build_config {
    runtime     = "python311"
    entry_point = "process_infographic_trigger"      
    
    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
        object = google_storage_bucket_object.upload_zip_traduzione_infografiche.name
      }
    }
  }

  service_config {
    max_instance_count               = 5
    max_instance_request_concurrency = 80
    available_memory                 = "2G" 
    available_cpu                    = "1" 
    timeout_seconds                  = 540
    service_account_email            = google_service_account.cloud_worker.email
  }

  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = google_service_account.cloud_worker.email
    
    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.infografica_input.name
    }
  }
}
resource "google_storage_bucket_iam_member" "eventarc_infografica_input_permissions" {
  bucket = google_storage_bucket.infografica_input.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}