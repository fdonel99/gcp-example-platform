locals {
  target_project_id = var.environment == "prod" ? "cloud-platform-northstar" : "cloud-platform-northstar-test"
}

data "google_project" "current_project" {
  project_id = local.target_project_id
}

resource "google_resource_manager_lien" "prevent_delete" {
  parent       = "projects/${data.google_project.current_project.number}"
  restrictions = ["resourcemanager.projects.delete"]
  origin       = "terraform-automation"
  reason       = "Vincolo di non eliminazione per ambiente ${upper(var.environment)}"
}