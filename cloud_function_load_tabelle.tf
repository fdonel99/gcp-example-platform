# --- CLOUD FUNCTIONS ---

#TABLES LOADING

data "archive_file" "zip_tables_loading" {
  type        = "zip"
  source_dir  = "${path.module}/src/tables_loading" 
  output_path = "${path.module}/src/tables_loading.zip"
}

resource "google_storage_bucket_object" "upload_zip_tables_loading" {
  name   = "tables_loading_${data.archive_file.zip_tables_loading.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_tables_loading.output_path
}

resource "google_cloudfunctions2_function" "function_tables_loading" {
  name        = "tables-loading-fn"
  location    = "europe-west1" 
  description = "Carica i dati importati da Drive in tabelle Big Query"

  build_config {
    runtime     = "python311" 
    entry_point = "run_sqlite_to_bigquery" 

    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
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
    service_account_email            = google_service_account.cloud_worker.email
  }
}

resource "null_resource" "mount_gcs_fuse_volume" {
  triggers = {
    function_id = google_cloudfunctions2_function.function_tables_loading.id
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud run services update ${google_cloudfunctions2_function.function_tables_loading.name} \
        --region=${google_cloudfunctions2_function.function_tables_loading.location} \
        --add-volume=name=bucket-zip,type=cloud-storage,bucket=bkt-export-ns-zip \
        --add-volume-mount=volume=bucket-zip,mount-path=/mnt/bucket \
        --execution-environment=gen2 \
        --quiet
    EOT
  }
}