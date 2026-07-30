# --- GESTIONE BUCKET CLOUD STORAGE ---

locals {
  # Una variabile locale per rendere il codice più pulito
  is_test = var.environment == "test" ? true : false
}

resource "google_storage_bucket" "anagrafica_prodotti" {
  project                     = var.project_id
  name                        = "bkt-anagrafica-prodotti-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}

resource "google_storage_bucket" "export_ns_zip" {
  project                     = var.project_id
  name                        = "bkt-export-ns-zip-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  versioning {
    enabled = true
  }
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      days_since_noncurrent_time = 21
    }
  }
}

resource "google_storage_bucket" "report_fornitori" {
  project                     = var.project_id
  name                        = "bkt-report-fornitori-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}

resource "google_storage_bucket" "spese_trasporto" {
  project                     = var.project_id
  name                        = "bkt-spese-trasporto-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 5
      matches_suffix = ["elaborato.xlsx"] 
    }
  }
}

resource "google_storage_bucket" "infografica_input" {
  project                     = var.project_id
  name                        = "bkt-infografica-input-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  lifecycle_rule {
    condition {
      age = 2
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "infografica_output" {
  project                     = var.project_id
  name                        = "bkt-infografica-output-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  lifecycle_rule {
    condition {
      age = 2
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "tf_state" {
  project                     = var.project_id
  name                        = "bkt-tf-state-for-transition-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  versioning {
    enabled = true
  }
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      days_since_noncurrent_time = 7
    }
  }
}

resource "google_storage_bucket_object" "file_statici_spese" {
  for_each = fileset("${path.module}/src/file_statici", "*")

  name   = each.value                                
  bucket = google_storage_bucket.spese_trasporto.name 
  source = "${path.module}/src/file_statici/${each.value}" 
}

resource "google_storage_bucket" "bucket_codice_funzioni" {
  project                     = var.project_id
  name                        = "bkt-functions-code-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}

resource "google_storage_bucket" "bucket_listino_costi_trasporto" {
  project                     = var.project_id
  name                        = "bkt-listino-costi-trasporto-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}