# --- GESTIONE BUCKET CLOUD STORAGE  ---

resource "google_storage_bucket" "anagrafica_prodotti" {
  name                        = "bkt-anagrafica-prodotti"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "export_ns_zip" {
  name                        = "bkt-export-ns-zip"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
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
  name                        = "bkt-report-fornitori"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "spese_trasporto" {
  name                        = "bkt-spese-trasporto"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
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
  name                        = "bkt-infografica-input"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
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
  name                        = "bkt-infografica-output"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
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
  name                        = "bkt-tf-state-for-transition"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
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
  name                        = "bkt-functions-code"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}