# --- GESTIONE PERMESSI IAM ---

resource "google_project_iam_member" "kommsrls_admin" {
  count   = var.environment == "prod" ? 1 : 0
  
  project = var.project_id
  role    = "roles/editor"
  member  = "user:kommsrls@gmail.com"
}

resource "google_project_iam_member" "kommsrls_billing_test" {
  count   = var.environment == "test" ? 1 : 0
  
  project = var.project_id
  role    = "roles/billing.projectManager" 
  member  = "user:kommsrls@gmail.com"
}

resource "google_project_iam_member" "jacopo_storage_admin" {
  for_each = var.environment == "prod" ? toset([
    "roles/storage.objectAdmin",          
    "roles/storage.bucketViewer"        
  ]) : toset([])
  
  project = var.project_id
  role    = each.value
  member  = "user:jacopo.donelli@northstaritaly.com"
}

resource "google_project_iam_member" "alberto_storage_admin" {
  for_each = var.environment == "prod" ? toset([
    "roles/storage.objectAdmin" ,          
    "roles/storage.bucketViewer"        
  ]) : toset([])
  
  project = var.project_id
  role    = each.value
  member  = "user:alberto.donelli@northstaritaly.com"
}

resource "google_project_iam_member" "donellifj_storage_admin" {
  for_each = var.environment == "prod" ? toset([
    "roles/storage.objectAdmin" ,          
    "roles/storage.bucketViewer"        
  ]) : toset([])
  
  project = var.project_id
  role    = each.value
  member  = "user:donellifjsrl@gmail.com"
}