# --- GESTIONE SERVICE ACCOUNT ---

# 1
resource "google_service_account" "cloud_worker" {
  account_id   = "cloud-functions-worker"
  display_name = "Service Account per Cloud Functions"
  description  = "Identità utilizzata dalle funzioni per accedere a Storage e BigQuery"
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
  
  project = "cloud-platform-northstar"
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_worker.email}"
}