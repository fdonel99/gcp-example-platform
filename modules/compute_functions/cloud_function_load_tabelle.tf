# TABLES LOADING

data "archive_file" "zip_tables_loading" {
  type        = "zip"
  source_dir  = "${path.module}/src/tables_loading" 
  output_path = "${path.module}/src/tables_loading.zip"
}

resource "google_storage_bucket_object" "upload_zip_tables_loading" {
  name   = "tables_loading_${data.archive_file.zip_tables_loading.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_tables_loading.output_path
}

resource "google_cloudfunctions2_function" "function_tables_loading" {
  project     = var.project_id
  name        = "tables-loading-fn-${var.environment}"
  location    = var.region 
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
    available_memory                 = "1Gi"
    available_cpu                    = "1"
    timeout_seconds                  = 3600
    max_instance_request_concurrency = 80
    service_account_email            = var.cloud_worker_sa_email
    environment_variables = {
      PROJECT_ID  = var.project_id
      DATASET_ID  = "NORTHSTAR"
      BUCKET_NAME = var.bucket_export_ns_zip_name
    }
  }
}

resource "null_resource" "mount_gcs_fuse_volume" {
  triggers = {
    function_id = google_cloudfunctions2_function.function_tables_loading.id
  }

  provisioner "local-exec" {
    # NOTA: Ho aggiunto il parametro --project e reso dinamico il nome del bucket
    command = <<EOT
      gcloud run services update ${google_cloudfunctions2_function.function_tables_loading.name} \
        --project=${var.project_id} \
        --region=${google_cloudfunctions2_function.function_tables_loading.location} \
        --add-volume=name=bucket-zip,type=cloud-storage,bucket=${var.bucket_export_ns_zip_name} \
        --add-volume-mount=volume=bucket-zip,mount-path=/mnt/bucket \
        --execution-environment=gen2 \
        --quiet
    EOT
  }
}