terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "cloud-platform-northstar"
  region  = "europe-west1"
}

# --- API ---

locals {
  gcp_services = [
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "eventarc.googleapis.com",
    "cloudscheduler.googleapis.com",       
    "bigquerydatatransfer.googleapis.com"  
  ]
}

resource "google_project_service" "api_necessarie" {
  for_each           = toset(local.gcp_services)
  project            = "cloud-platform-northstar"
  service            = each.value
  disable_on_destroy = false # Evita di spegnere le API se distruggi le risorse in futuro
}

# --- GESTIONE ACCESSI ---

# IAM

#1
resource "google_project_iam_member" "kommsrls_admin" {
  project = "cloud-platform-northstar"
  role    = "roles/editor"
  member  = "user:kommsrls@gmail.com"
}

# 2
resource "google_project_iam_member" "jacopo_storage_admin" {
  project = "cloud-platform-northstar"
  role    = "roles/storage.objectAdmin"
  member  = "user:jacopo.donelli@northstaritaly.com"
}

# 3
resource "google_project_iam_member" "alberto_storage_admin" {
  project = "cloud-platform-northstar"
  role    = "roles/storage.objectAdmin"
  member  = "user:alberto.donelli@northstaritaly.com"
}

# SERVICE ACCOUNT

# 1
resource "google_service_account" "cloud_worker" {
  account_id   = "cloud-functions-worker"
  display_name = "Service Account per Cloud Functions"
  description  = "Identità utilizzata dalle funzioni per accedere a Storage e BigQuery"
}

locals {
  worker_roles = [
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/storage.objectAdmin",
    "roles/run.invoker",
    "roles/eventarc.eventReceiver"
  ]
}

resource "google_project_iam_member" "cloud_worker_permissions" {
  for_each = toset(local.worker_roles)
  
  project = "cloud-platform-northstar"
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_worker.email}"
}

# PERMESSO EVENTARC PER IL BUCKET SPESE TRASPORTO 

# Concediamo i permessi di lettura oggetti al Service Account di sistema di Google Cloud Storage per Eventarc
resource "google_storage_bucket_iam_member" "eventarc_storage_permissions" {
  bucket = google_storage_bucket.spese_trasporto.name
  role   = "roles/storage.objectViewer"
  
  # Utilizziamo l'identificativo standard del service agent di storage/eventarc nel progetto
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

# Recupera il numero del progetto in automatico
data "google_project" "current" {}

# PERMESSO STORAGE PER EVENTARC / PUBSUB 

# Concede al servizio di Storage del progetto il permesso di pubblicare su Pub/Sub
resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = "cloud-platform-northstar"
  role    = "roles/pubsub.publisher"
  
  # Identificativo standard ufficiale del service account di Cloud Storage su Google Cloud
  member = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# --- GESTIONE DATASET ---

# NORTHSTAR

resource "google_bigquery_dataset" "dataset_principale" {
  dataset_id                  = "NORTHSTAR" 
  friendly_name               = "Database Northstar"
  description                 = "Dataset principale per l'importazione e analisi dati"
  location                    = "EU"
  delete_contents_on_destroy = false 
}

# --- GESTIONE BUCKET CLOUD STORAGE  ---

resource "google_storage_bucket" "anagrafica_prodotti" {
  name                        = "bkt-anagrafica-prodotti"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "export_ns_zip" {
  name                        = "bkt-export-ns-zip"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "report_fornitori" {
  name                        = "bkt-report-fornitori"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "spese_trasporto" {
  name                        = "bkt-spese-trasporto"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# CARICAMENTO FILE STATICI NEL BUCKET SPESE TRASPORTO
resource "google_storage_bucket_object" "file_statici_spese" {
  for_each = fileset("${path.module}/src/file_statici", "*")

  name   = each.value                                
  bucket = google_storage_bucket.spese_trasporto.name 
  source = "${path.module}/src/file_statici/${each.value}" 
}

resource "google_storage_bucket" "traduzione_immagini" {
  name                        = "bkt-traduzione-immagini"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "bucket_codice_funzioni" {
  name                        = "bkt-functions-code"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# --- CLOUD FUNCTIONS ---

#DRIVE TO GCP

data "archive_file" "zip_drive_to_gcp" {
  type        = "zip"
  source_dir  = "${path.module}/src/drive_to_gcp" 
  output_path = "${path.module}/src/drive_to_gcp.zip"
}

resource "google_storage_bucket_object" "upload_zip_drive_to_gcp" {
  name   = "drive_to_gcp_${data.archive_file.zip_drive_to_gcp.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_drive_to_gcp.output_path
}

resource "google_cloudfunctions2_function" "function_drive_to_gcp" {
  name        = "drive-to-gcp-fn"
  location    = "europe-west1" 
  description = "Importa dati da Google Drive a GCP"

  build_config {
    runtime     = "python311" 
    
    entry_point = "drive_to_gcp" 

    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
        object = google_storage_bucket_object.upload_zip_drive_to_gcp.name
      }
    }
  }

  service_config {
    min_instance_count               = 0
    max_instance_count               = 5
    available_memory                 = "1G"
    available_cpu                    = "1"
    timeout_seconds                  = 300
    max_instance_request_concurrency = 80
    service_account_email = google_service_account.cloud_worker.email
  }
}

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
    available_memory                 = "16G"
    available_cpu                    = "4"
    timeout_seconds                  = 3600
    max_instance_request_concurrency = 80
    service_account_email = google_service_account.cloud_worker.email
  }
}

#SPESE TRASPORTO

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

  # BLOCCO TRIGGER DA CLOUD STORAGE
  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = google_service_account.cloud_worker.email
    
    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.spese_trasporto.name
    }
  }
}