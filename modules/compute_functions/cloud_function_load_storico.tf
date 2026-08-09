data "archive_file" "zip_load_storico" {
  type        = "zip"
  source_dir  = "${path.module}/src/load_storico" 
  output_path = "${path.module}/src/load_storico.zip"
}

resource "google_storage_bucket_object" "upload_zip_load_storico" {
  name   = "load_storico_${data.archive_file.zip_load_storico.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_load_storico.output_path
}

# --- 3. Definizione della Cloud Function ---
resource "google_cloudfunctions2_function" "function_load_storico" {
  project     = var.project_id
  name        = "load-storico-fn-${var.environment}"
  location    = var.region 
  labels = {
    scopo = "fn-caricamento-storico"
  }
  description = "Estrae il file storico da Drive e fa il dump in BQ (${var.environment})"

  build_config {
    runtime     = "python311" 
    entry_point = "run_load_storico" 

    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
        object = google_storage_bucket_object.upload_zip_load_storico.name 
      }
    }
  }

  service_config {
    min_instance_count               = 0
    max_instance_count               = 1     
    available_memory                 = "8Gi" 
    available_cpu                    = "2"   
    timeout_seconds                  = 3600  
    max_instance_request_concurrency = 1
    service_account_email            = var.cloud_worker_sa_email
    
    environment_variables = {
      DATASET_STORICO_ID   = "NORTHSTAR_STORICO"
      BUCKET_NAME          = var.bucket_import_ns_zip_name
      FOLDER_ID            = "1ujC-hbN_haUjrg8b3kLVrML0ad_UwTlO"
      SHEET_ID             = "1ptH6m4mS6UozgrtRUfoP_wMMwbx7wTiIn1T6eJ0Vy1c" 
      GOOGLE_CLOUD_PROJECT = var.project_id
    }

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

# --- 4. Montaggio Volume GCS Fuse per poggiare i file parquet temporanei ---
resource "null_resource" "mount_gcs_fuse_volume_storico" {
  triggers = {
    function_id = google_cloudfunctions2_function.function_load_storico.id
    bucket_name = var.bucket_import_ns_zip_name
    codice_hash = data.archive_file.zip_load_storico.output_md5
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud run services update ${google_cloudfunctions2_function.function_load_storico.name} \
        --project=${var.project_id} \
        --region=${google_cloudfunctions2_function.function_load_storico.location} \
        --add-volume=name=bucket-zip,type=cloud-storage,bucket=${var.bucket_import_ns_zip_name} \
        --add-volume-mount=volume=bucket-zip,mount-path=/mnt/bucket \
        --execution-environment=gen2 \
        --quiet
    EOT
  }
}