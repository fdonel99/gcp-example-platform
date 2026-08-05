# --- BACKEND ---
terraform {
  backend "gcs" {
    bucket  = "bkt-tf-state-for-transition" 
    prefix  = "terraform/state/prod"
  }
}