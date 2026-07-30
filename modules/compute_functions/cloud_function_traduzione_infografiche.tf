# TRADUZIONE INFOGRAFICHE 

data "archive_file" "zip_traduzione_infografiche" {
  type        = "zip"
  source_dir  = "${path.module}/src/traduzione_infografiche" 
  output_path = "${path.module}/src/traduzione_infografiche.zip"
}

resource "google_storage_bucket_object" "upload_zip_traduzione_infografiche" {
  name   = "traduzione_infografiche_${data.archive_file.zip_traduzione_infografiche.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_traduzione_infografiche.output_path
}

resource "google_cloudfunctions2_function" "function_traduzione_infografiche" {
  project     = var.project_id
  name        = "traduzione-infografiche-fn-${var.environment}"
  location    = var.region
  description = "Trigger file input per la pipeline delle infografiche (${var.environment})"
  
  build_config {
    runtime     = "python311"
    entry_point = "process_infographic_trigger"      
    
    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
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
    service_account_email            = var.cloud_worker_sa_email
    environment_variables = {
      PROJECT_ID         = var.project_id
      REGION             = var.region
      OUTPUT_BUCKET_NAME = var.bucket_infografica_output_name 
    }
  }

  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = var.cloud_worker_sa_email
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
    
    event_filters {
      attribute = "bucket"
      # Sostituito con la variabile del bucket di input infografiche
      value     = var.bucket_infografica_input_name
    }
  }
}

resource "google_storage_bucket_iam_member" "eventarc_infografica_input_permissions" {
  bucket = var.bucket_infografica_input_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}