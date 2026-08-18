# SPESE DI TRASPORTO

data "archive_file" "zip_calcolo_spese_trasporto"  {
  type        = "zip"
  source_dir  = "${path.module}/src/calcolo_spese_trasporto" 
  output_path = "${path.module}/src/calcolo_spese_trasporto.zip"
}

resource "google_storage_bucket_object" "upload_zip_calcolo_spese_trasporto" {
  name   = "calcolo_spese_trasporto_${data.archive_file.zip_calcolo_spese_trasporto.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_calcolo_spese_trasporto.output_path
}

resource "google_cloudfunctions2_function" "function_calcolo_spese_trasporto" {
  project     = var.project_id
  name        = "calcolo-spese-trasporto-fn-${var.environment}"
  location    = var.region
  labels = {
    scopo       = "fn-calcolo-spese-trasporto"
  }
  build_config {
    runtime     = "python311"
    entry_point = "calcola_spese_trasporto"      
    
    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
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
    service_account_email            = var.cloud_worker_sa_email
    environment_variables = {
      SPREADSHEET_ID = "1TYpxmD6H_9v-ZeeOqSZqiHF50cyzj6xpg51zTaTEQWE",
      DEPLOY_HASH    = data.archive_file.zip_calcolo_spese_trasporto.output_md5
    }
  }

  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = var.cloud_worker_sa_email
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    
    event_filters {
      attribute = "bucket"
      value     = var.bucket_spese_trasporto_name
    }
  }
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_storage_bucket_iam_member" "eventarc_storage_permissions" {
  bucket = var.bucket_spese_trasporto_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = var.project_id 
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}