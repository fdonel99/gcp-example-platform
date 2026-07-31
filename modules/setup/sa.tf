# --- GESTIONE SERVICE ACCOUNT ---

# WORKER
resource "google_service_account" "cloud_worker" {
  account_id   = "cloud-worker-${var.environment}"
  display_name = "Service Account per Cloud Functions (${var.environment})"
  description  = "Identità utilizzata dalle funzioni per accedere a Storage e BigQuery"
  project      = var.project_id 
}

locals {
  worker_roles = [
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/storage.objectAdmin",
    "roles/run.invoker",
    "roles/eventarc.eventReceiver",
    "roles/aiplatform.user"
  ]
}

resource "google_project_iam_member" "cloud_worker_permissions" {
  for_each = toset(local.worker_roles)
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_worker.email}"
}

# DEPLOYER
resource "google_service_account" "cloud_deployer" {
  account_id   = "cloud-deployer-${var.environment}"
  display_name = "GitHub Actions Service Account (${var.environment})"
  description  = "Identità con ruolo Editor utilizzata da GitHub Actions per eseguire Terraform"
  project      = var.project_id
}

resource "google_project_iam_member" "github_cloud_deployer_editor" {
  project = var.project_id
  for_each = toset([
    "roles/editor",          
    "roles/resourcemanager.projectIamAdmin"        
  ])
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_deployer.email}"
}