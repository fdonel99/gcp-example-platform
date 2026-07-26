# --- GESTIONE PERMESSI IAM ---

#1
resource "google_project_iam_member" "kommsrls_admin" {
  project = "cloud-platform-northstar"
  role    = "roles/editor"
  member  = "user:kommsrls@gmail.com"
}

# 2
resource "google_project_iam_member" "jacopo_storage_admin" {
  project = "cloud-platform-northstar"
  role    = "roles/storage.objectAdmin"
  member  = "user:jacopo.donelli@northstaritaly.com"
}

# 3
resource "google_project_iam_member" "alberto_storage_admin" {
  project = "cloud-platform-northstar"
  role    = "roles/storage.objectAdmin"
  member  = "user:alberto.donelli@northstaritaly.com"
}