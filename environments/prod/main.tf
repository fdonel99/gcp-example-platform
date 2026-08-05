# --- AMBIENTE DI PRODUZIONE ---

# environments/prod/main.tf

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0" 
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =======================================================
# 1. SETUP: API e Service Account
# =======================================================
module "setup" {
  source                 = "../../modules/setup"
  project_id             = var.project_id
  environment            = var.environment
  telegram_token_value   = var.telegram_token_value
  telegram_chat_id_value = var.telegram_chat_id
}

# =======================================================
# 2. DATA STORAGE: Dataset e Bucket
# =======================================================
module "data_storage" {
  source      = "../../modules/data_storage"
  project_id  = var.project_id
  environment = var.environment
}

# =======================================================
# 3. COMPUTE FUNCTIONS: Funzioni Serverless
# =======================================================
module "compute_functions" {
  source                              = "../../modules/compute_functions"
  project_id                          = var.project_id
  region                              = var.region
  environment                         = var.environment
  
  cloud_worker_sa_email               = module.setup.cloud_worker_sa_email
  bucket_codice_funzioni_name         = module.data_storage.bucket_codice_funzioni_name
  bucket_export_ns_zip_name           = module.data_storage.bucket_export_ns_zip_name
  bucket_spese_trasporto_name         = module.data_storage.bucket_spese_trasporto_name
  bucket_infografica_input_name       = module.data_storage.bucket_infografica_input_name
  bucket_infografica_output_name      = module.data_storage.bucket_infografica_output_name
  bucket_listino_costi_trasporto_name = module.data_storage.bucket_listino_costi_trasporto_name
  
  telegram_secret_name                = module.setup.telegram_secret_name
  telegram_chat_id_secret_name        = module.setup.telegram_chat_id_secret_name
}

# =======================================================
# 4. ORCHESTRATION: Scheduler e Query
# =======================================================
module "orchestration" {
  source                          = "../../modules/orchestration"
  project_id                      = var.project_id
  region                          = var.region
  environment                     = var.environment
  
  # Variabili passate dagli ALTRI moduli:
  cloud_worker_sa_email           = module.setup.cloud_worker_sa_email
  bucket_anagrafica_prodotti_name = module.data_storage.bucket_anagrafica_prodotti_name
  bucket_report_fornitori_name    = module.data_storage.bucket_report_fornitori_name
  bucket_export_ns_zip_name       = module.data_storage.bucket_export_ns_zip_name
  
  drive_folder_id                 = var.drive_folder_id 
  
  # URI generati dal modulo Compute Functions
  function_drive_to_gcp_uri       = module.compute_functions.function_drive_to_gcp_uri
  function_tables_loading_uri     = module.compute_functions.function_tables_loading_uri
  cf_scheduler_sa_email           = module.setup.cf_scheduler_sa_email
  bq_scheduler_sa_email           = module.setup.bq_scheduler_sa_email
}