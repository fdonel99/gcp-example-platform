# --- GESTIONE PROVIDERS ---

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0.0"
    }
  }
}

provider "google" {
  project = "cloud-platform-northstar"
  region  = "europe-west1"
}

provider "google-beta" {
  project = "cloud-platform-northstar"
  region  = "europe-west1"
}