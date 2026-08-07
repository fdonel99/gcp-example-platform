# --- CLOUD FUNCTIONS ---

# REPORT FORNITORI

data "archive_file" "zip_report_fornitori" {
  type        = "zip"
  source_dir  = "${path.module}/src/report_fornitori" 
  output_path = "${path.module}/src/report_fornitori.zip"
}

resource "google_storage_bucket_object" "upload_zip_report_fornitori" {
  name   = "report_fornitori_${data.archive_file.zip_report_fornitori.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_report_fornitori.output_path
}

resource "google_cloudfunctions2_function" "function_report_fornitori" {
  project     = var.project_id
  name        = "report-fornitori-fn-${var.environment}"
  location    = var.region 
  
  labels = {
    scopo = "fn-report-fornitori"
  }
  
  description = "Genera il Report Fornitori da BQ a Google Sheets (${var.environment})"

  build_config {
    runtime     = "python311" 
    entry_point = "report_fornitori" 

    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
        object = google_storage_bucket_object.upload_zip_report_fornitori.name
      }
    }
  } 

  service_config {
    min_instance_count               = 0
    max_instance_count               = 5
    available_memory                 = "2G"  
    available_cpu                    = "1"
    timeout_seconds                  = 540   
    max_instance_request_concurrency = 1     
    
    service_account_email            = var.cloud_worker_sa_email
    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
    }
  }
}