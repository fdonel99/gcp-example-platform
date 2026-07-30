# --- GESTIONE PERMESSI IAM ---

# 1. Accesso Editor per Komm Srls
resource "google_project_iam_member" "kommsrls_admin" {
  project = var.project_id
  role    = "roles/editor"
  member  = "user:kommsrls@gmail.com"
}

# 2. Permessi Storage per Jacopo
resource "google_project_iam_member" "jacopo_storage_admin" {
  project = var.project_id
  for_each = toset([
    "roles/storage.objectAdmin",          
    "roles/storage.bucketViewer"        
  ])
  role    = each.value
  member  = "user:jacopo.donelli@northstaritaly.com"
}

# 3. Permessi Storage per Alberto
resource "google_project_iam_member" "alberto_storage_admin" {
  project = var.project_id
  for_each = toset([
    "roles/storage.objectAdmin",          
    "roles/storage.bucketViewer"        
  ])
  role    = each.value
  member  = "user:alberto.donelli@northstaritaly.com"
}