# --- GESTIONE BUCKET CLOUD STORAGE ---

locals {
  # Una variabile locale per rendere il codice più pulito
  is_test = var.environment == "test" ? true : false
}

resource "google_storage_bucket" "import_ns_zip" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-import-ns-zip" : "bkt-import-ns-zip-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test

  labels = {
    scopo = "bkt-zip-tabelle"
  }

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

resource "google_storage_bucket" "spese_trasporto" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-spese-trasporto" : "bkt-spese-trasporto-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test

  labels = {
    scopo = "bkt-calcolo-spese-trasporto"
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 5
      matches_suffix = ["elaborato.xlsx", "elaborato.csv"]
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

  labels = {
    scopo = "bkt-input-infografiche"
  }

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

  labels = {
    scopo = "bkt-output-infografiche"
  }

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "bucket_codice_funzioni" {
  project                     = var.project_id
  name                        = var.environment == "prod" ? "bkt-functions-code" : "bkt-functions-code-${var.project_id}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test
  
  labels = {
    scopo = "bkt-codice-funzioni"
  }

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

  labels = {
    scopo = "bkt-listino-costi-trasporto"
  }
}

/*
# =======================================================
# BUCKET DI STATO (GESTITO MANUALMENTE DA CONSOLE)
# =======================================================
# Questo blocco è lasciato qui solo a scopo documentale.
# Il bucket reale è configurato direttamente su Google Cloud 
# per evitare conflitti con l'inizializzazione del backend.

resource "google_storage_bucket" "tf_state" {
  project                     = var.project_id
  name                        = "bkt-tf-state-for-transition-${var.environment}"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = local.is_test

  labels = {
    scopo = "bkt-tf-state"
  }

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
*/