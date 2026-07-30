variable "project_id" {
  type        = string
  description = "ID del progetto GCP di Produzione"
  default     = "cloud-platform-northstar" # Inserisci il vero ID se diverso
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