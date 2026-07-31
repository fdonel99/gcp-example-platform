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