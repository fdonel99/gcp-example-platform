variable "project_id" {
  type        = string
  description = "L'ID del progetto GCP"
}

variable "environment" {
  type        = string
  description = "Ambiente di rilascio (es. prod, test)"
}

variable "cloud_worker_sa_email" {
  type        = string
  description = "L'email del Service Account Worker generata nel modulo setup"
}

variable "bucket_anagrafica_prodotti_name" {
  type        = string
  description = "Nome del bucket dove salvare le anagrafiche (generato nel modulo storage)"
}

variable "bucket_report_fornitori_name" {
  type        = string
  description = "Nome del bucket dove salvare i report (generato nel modulo storage)"
}

variable "region" {
  type        = string
  description = "La region in cui fare il deploy dello scheduler"
  default     = "europe-west1"
}

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