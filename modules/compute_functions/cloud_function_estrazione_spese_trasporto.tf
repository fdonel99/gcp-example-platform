data "archive_file" "zip_estrazione_spese_trasporto"  {
  type        = "zip"
  source_dir  = "${path.module}/src/estrazione_spese_trasporto" 
  output_path = "${path.module}/src/estrazione_spese_trasporto.zip"
}
resource "google_storage_bucket_object" "upload_zip_estrazione_spese_trasporto" {
  name   = "estrazione_spese_trasporto_${data.archive_file.zip_estrazione_spese_trasporto.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_estrazione_spese_trasporto.output_path
}

resource "google_cloudfunctions2_function" "function_estrazione_spese_trasporto" {
  project     = var.project_id
  name        = "estrazione-spese-trasporto-fn-${var.environment}" 
  location    = var.region
    labels = {
    scopo       = "fn-estrazione-listino-trasporto"
  }
  build_config {
    runtime     = "python311"
    entry_point = "estrai_tariffe_pdf"
    
    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
        object = google_storage_bucket_object.upload_zip_estrazione_spese_trasporto.name
      }
    }
  }

  service_config {
    max_instance_count               = 5
    max_instance_request_concurrency = 1
    available_memory                 = "2G"
    timeout_seconds                  = 300
    available_cpu                    = "1" 
    service_account_email            = var.cloud_worker_sa_email

    environment_variables = {
      PROJECT_ID         = var.project_id
      LOCATION           = var.region
      SPREADSHEET_ID = "1TYpxmD6H_9v-ZeeOqSZqiHF50cyzj6xpg51zTaTEQWE"
      DEPLOY_HASH    = data.archive_file.zip_estrazione_spese_trasporto.output_md5
    }
  }

  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = var.cloud_worker_sa_email
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    
    event_filters {
      attribute = "bucket"
      value     = var.bucket_listino_costi_trasporto_name
    }
  }
}

# --- PERMESSI IAM PER I TRIGGER EVENTARC ---

data "google_project" "current_estrazione_spese" {
  project_id = var.project_id
}

resource "google_storage_bucket_iam_member" "eventarc_storage_permissions_estrazione_spese" {
  bucket = var.bucket_listino_costi_trasporto_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current_estrazione_spese.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "storage_pubsub_publisher_estrazione_spese" {
  project = var.project_id 
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current_estrazione_spese.number}@gs-project-accounts.iam.gserviceaccount.com"
}