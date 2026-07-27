# --- CLOUD FUNCTIONS ---

#SPESE DI TRASPORTO

data "archive_file" "zip_calcolo_spese_trasporto" {
  type        = "zip"
  source_dir  = "${path.module}/src/calcolo_spese_trasporto" 
  output_path = "${path.module}/src/calcolo_spese_trasporto.zip"
  
}

resource "google_storage_bucket_object" "upload_zip_calcolo_spese_trasporto" {
  name   = "calcolo_spese_trasporto_${data.archive_file.zip_calcolo_spese_trasporto.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_calcolo_spese_trasporto.output_path
}

resource "google_cloudfunctions2_function" "function_calcolo_spese_trasporto" {
  name        = "calcolo-spese-trasporto-fn"
  location    = "europe-west1"
  
  build_config {
    runtime     = "python311"
    entry_point = "elabora_spese_trasporto"      
    
    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
        object = google_storage_bucket_object.upload_zip_calcolo_spese_trasporto.name
      }
    }
  }

  service_config {
    max_instance_count               = 5
    max_instance_request_concurrency = 80
    available_memory                 = "1G" 
    available_cpu                    = "1" 
    timeout_seconds                  = 60
    service_account_email = google_service_account.cloud_worker.email
  }

  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = google_service_account.cloud_worker.email
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    
    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.spese_trasporto.name
    }
  }
}
resource "google_storage_bucket_iam_member" "eventarc_storage_permissions" {
  bucket = google_storage_bucket.spese_trasporto.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

data "google_project" "current" {}

resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = "cloud-platform-northstar"
  role    = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}