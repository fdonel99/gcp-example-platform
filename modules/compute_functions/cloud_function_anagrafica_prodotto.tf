# --- CLOUD FUNCTIONS ---

# ANAGRAFICA PRODOTTO

data "archive_file" "zip_anagrafica_prodotto" {
  type        = "zip"
  source_dir  = "${path.module}/src/anagrafica_prodotto" 
  output_path = "${path.module}/src/anagrafica_prodotto.zip"
}

resource "google_storage_bucket_object" "upload_zip_anagrafica_prodotto" {
  name   = "anagrafica_prodotto_${data.archive_file.zip_anagrafica_prodotto.output_md5}.zip"
  bucket = var.bucket_codice_funzioni_name
  source = data.archive_file.zip_anagrafica_prodotto.output_path
}

resource "google_cloudfunctions2_function" "function_anagrafica_prodotto" {
  project     = var.project_id
  name        = "anagrafica-prodotto-fn-${var.environment}"
  location    = var.region 
  
  labels = {
    scopo = "fn-anagrafica-prodotto"
  }
  
  description = "Esporta Anagrafica Prodotto da BQ a Google Drive in formato Excel (${var.environment})"

  build_config {
    runtime     = "python311" 
    entry_point = "anagrafica_prodotto" 

    source {
      storage_source {
        bucket = var.bucket_codice_funzioni_name
        object = google_storage_bucket_object.upload_zip_anagrafica_prodotto.name
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