variable "project_id" {
  type        = string
  description = "L'ID del progetto GCP"
}

variable "environment" {
  type        = string
  description = "Ambiente di rilascio (es. prod, test)"
}

variable "region" {
  type        = string
  description = "La region in cui fare il deploy delle funzioni"
  default     = "europe-west1"
}

variable "cloud_worker_sa_email" {
  type        = string
  description = "L'email del Service Account Worker generata nel modulo setup"
}

variable "bucket_codice_funzioni_name" {
  type        = string
  description = "Il nome del bucket dove caricare i file .zip delle funzioni"
}

variable "bucket_import_ns_zip_name" {
  type        = string
  description = "Il nome del bucket per l'import degli ZIP (usato per il mount GCS FUSE)"
}

variable "bucket_spese_trasporto_name" {
  type        = string
  description = "Il nome del bucket delle spese di trasporto (usato per il trigger Eventarc)"
}

variable "bucket_infografica_input_name" {
  type        = string
  description = "Il nome del bucket di input per le infografiche (usato per il trigger Eventarc)"
}

variable "bucket_infografica_output_name" {
  type        = string
  description = "Il nome del bucket di output dove salvare le infografiche tradotte"
}

variable "bucket_listino_costi_trasporto_name" {
  type        = string
  description = "Il nome del bucket di input per i listini PDF (usato per il trigger Eventarc)"
}

variable "telegram_secret_name" {
  type        = string
  description = "Nome del secret di Secret Manager per il token Telegram"
}

variable "telegram_chat_id_secret_name" {
  type        = string
  description = "Nome del secret per la Chat ID Telegram"
}

variable "folder_id_storico" {
  type        = string
  description = "L'ID della cartella Google Drive contenente il file ZIP dello storico (es. 2023-2024-2025.zip)"
}