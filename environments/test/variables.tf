variable "project_id" {
  type        = string
  description = "ID del progetto GCP di Test"
  default     = "cloud-platform-northstar-test" # Sostituisci con il VERO ID del progetto di test!
}

variable "region" {
  type        = string
  description = "Region di default"
  default     = "europe-west1"
}

variable "environment" {
  type        = string
  description = "Ambiente di esecuzione"
  default     = "test" 
}

variable "telegram_token_value" {
  description = "Il token del bot Telegram da salvare in Secret Manager"
  type        = string
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "L'ID della chat o del gruppo Telegram a cui inviare le notifiche"
  type        = string
}

variable "drive_folder_id" {
  description = "L'ID della cartella Google Drive da cui estrarre i file"
  type        = string
}