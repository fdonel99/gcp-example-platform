# --- MAIN ---

terraform {
  backend "gcs" {
    bucket  = "bkt-tf-state-for-transition-test" 
    prefix  = "terraform/state/test"
  }
}