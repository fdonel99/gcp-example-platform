variable "project_id" {
  type        = string
  description = "ID del progetto GCP di Produzione"
  default     = "cloud-platform-northstar" 
}

variable "region" {
  type        = string
  description = "Region di default"
  default     = "europe-west1"
}

variable "environment" {
  type        = string
  description = "Ambiente di esecuzione"
  default     = "prod"
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
  default     = "1uHYaM5wGusC2GY7v-Vp-xIq5U0KcZ8FJ"
}

variable "folder_id_storico" {
  type        = string
  description = "L'ID della cartella Google Drive contenente lo storico"
  default = "1ujC-hbN_haUjrg8b3kLVrML0ad_UwTlO"
}