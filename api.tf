# --- GESTIONE API ---

locals {
  gcp_services = [
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "eventarc.googleapis.com",
    "cloudscheduler.googleapis.com",       
    "bigquerydatatransfer.googleapis.com",
    "vision.googleapis.com",
    "translate.googleapis.com",
    "aiplatform.googleapis.com",
    "drive.googleapis.com"  
  ]
}

resource "google_project_service" "api_necessarie" {
  for_each           = toset(local.gcp_services)
  project            = "cloud-platform-northstar"
  service            = each.value
  disable_on_destroy = false # Evita di spegnere le API se distruggi le risorse in futuro
}