# --- AMBIENTE DI TEST ---

# environments/test/main.tf

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0" 
    }
  }
}

# =======================================================
# 1. SETUP: API e Service Account
# =======================================================
module "setup_progetto" {
  source     = "../../modules/setup"
  project_id = var.project_id
  environment = var.environment
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
  source                         = "../../modules/compute_functions"
  project_id                     = var.project_id
  region                         = var.region
  environment                    = var.environment
  
  # Variabili passate dagli ALTRI moduli:
  cloud_worker_sa_email          = module.setup_progetto.cloud_worker_sa_email
  bucket_codice_funzioni_name    = module.data_storage.bucket_codice_funzioni_name
  bucket_export_ns_zip_name      = module.data_storage.bucket_export_ns_zip_name
  bucket_spese_trasporto_name    = module.data_storage.bucket_spese_trasporto_name
  bucket_infografica_input_name  = module.data_storage.bucket_infografica_input_name
  bucket_infografica_output_name = module.data_storage.bucket_infografica_output_name
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
  cloud_worker_sa_email           = module.setup_progetto.cloud_worker_sa_email
  bucket_anagrafica_prodotti_name = module.data_storage.bucket_anagrafica_prodotti_name
  bucket_report_fornitori_name    = module.data_storage.bucket_report_fornitori_name
  bucket_export_ns_zip_name       = module.data_storage.bucket_export_ns_zip_name
  
  # URI generati dal modulo Compute Functions
  function_drive_to_gcp_uri       = module.compute_functions.function_drive_to_gcp_uri
  function_tables_loading_uri     = module.compute_functions.function_tables_loading_uri
}