# ID PROGETTO
variable "project_id" {
  type        = string
  description = "L'ID del progetto GCP"
}

# ENVIRONMENT
variable "environment" {
  type        = string
  description = "Ambiente di rilascio (es. prod, test)"
}

#EMAIL SERVICE ACCOUNT
variable "cloud_worker_sa_email" {
  type        = string
  description = "email del Service Account Worker generata nel modulo setup"
}

variable "bq_scheduler_sa_email" {
  type        = string
  description = "email del Service Account dedicato al query planner"
}

variable "cf_scheduler_sa_email" {
  type        = string
  description = "email del Service Account dedicato allo scheduler di BigQuery"
}

#BUCKET
variable "bucket_anagrafica_prodotti_name" {
  type        = string
  description = "Nome del bucket dove salvare le anagrafiche (generato nel modulo storage)"
}

variable "bucket_report_fornitori_name" {
  type        = string
  description = "Nome del bucket dove salvare i report (generato nel modulo storage)"
}

#CLOUD FUNCTIONS
variable "function_drive_to_gcp_uri" {
  type        = string
  description = "L'URI della Cloud Function Drive to GCP (generata nel modulo compute)"
}

variable "function_tables_loading_uri" {
  type        = string
  description = "L'URI della Cloud Function Tables Loading (generata nel modulo compute)"
}

variable "bucket_export_ns_zip_name" {
  type        = string
  description = "Il nome del bucket per l'export degli ZIP (passato allo scheduler per la funzione Drive to GCP)"
}

#REGION
variable "region" {
  type        = string
  description = "La region in cui fare il deploy"
  default     = "europe-west1"
}