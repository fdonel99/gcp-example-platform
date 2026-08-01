# --- GESTIONE BUCKET CLOUD STORAGE ---

locals {
  # Una variabile locale per rendere il codice più pulito
  is_test = var.environment == "test" ? true : false
}

resource "google_storage_bucket" "anagrafica_prodotti" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-anagrafica-prodotti" : "bkt-anagrafica-prodotti-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}

resource "google_storage_bucket" "export_ns_zip" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-export-ns-zip" : "bkt-export-ns-zip-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  versioning {
    enabled = local.is_test
  }
  dynamic "lifecycle_rule" {
    for_each = local.is_test ? [1] : []
    
    content {
      action {
        type = "Delete"
      }
      condition {
        days_since_noncurrent_time = 21
      }
    }
  }
}

resource "google_storage_bucket" "report_fornitori" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-report-fornitori" : "bkt-report-fornitori-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}

resource "google_storage_bucket" "spese_trasporto" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-spese-trasporto" : "bkt-spese-trasporto-${var.project_id}"
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
      matches_suffix = ["elaborato.xlsx", ".csv"]
    }
  }
}

resource "google_storage_bucket" "infografica_input" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-infografica-input" : "bkt-infografica-input-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "infografica_output" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-infografica-output" : "bkt-infografica-output-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "tf_state" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-tf-state-for-transition" : "bkt-tf-state-for-transition-${var.project_id}"
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
      days_since_noncurrent_time = local.is_test ? 7 : 90
    }
  }
}

resource "google_storage_bucket_object" "file_statici_spese"  {
  for_each = fileset("${path.module}/../compute_functions/src/file_statici", "*")

  name   = each.value                                
  bucket = google_storage_bucket.spese_trasporto.name 
  source = "${path.module}/../compute_functions/src/file_statici/${each.value}"
  detect_md5hash = filemd5("${path.module}/../compute_functions/src/file_statici/${each.value}")
}

resource "google_storage_bucket" "bucket_codice_funzioni" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-functions-code" : "bkt-functions-code-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  
  dynamic "lifecycle_rule" {
    for_each = local.is_test ? [1] : []
    
    content {
      action {
        type = "Delete"
      }
      condition {
        age            = 7           
        matches_suffix = [".zip"]   
      }
    }
  }
} 

resource "google_storage_bucket" "bucket_listino_costi_trasporto" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-listino-costi-trasporto" : "bkt-listino-costi-trasporto-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
}