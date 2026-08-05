variable "project_id" {
  description = "L'ID del progetto GCP"
  type        = string
}

variable "environment" {
  description = "L'ambiente di deploy (es. prod, test)"
  type        = string
}

variable "telegram_token_value" {
  description = "Il token del bot Telegram passato dall'ambiente principale"
  type        = string
  sensitive   = true
}

variable "telegram_chat_id_value" {
  description = "L'ID della chat Telegram da salvare nel Secret Manager"
  type        = string
  sensitive   = true
}