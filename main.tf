terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "cloud-platform-northstar"
  region  = "europe-west1"
}

# --- API ---

locals {
  gcp_services = [
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "eventarc.googleapis.com",
    "cloudscheduler.googleapis.com",       
    "bigquerydatatransfer.googleapis.com"  
  ]
}

resource "google_project_service" "api_necessarie" {
  for_each           = toset(local.gcp_services)
  project            = "cloud-platform-northstar"
  service            = each.value
  disable_on_destroy = false # Evita di spegnere le API se distruggi le risorse in futuro
}

# --- GESTIONE ACCESSI ---

# IAM

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

# SERVICE ACCOUNT

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
    "roles/eventarc.eventReceiver"
  ]
}

resource "google_project_iam_member" "cloud_worker_permissions" {
  for_each = toset(local.worker_roles)
  
  project = "cloud-platform-northstar"
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_worker.email}"
}

# --- GESTIONE DATASET ---

# NORTHSTAR

resource "google_bigquery_dataset" "dataset_principale" {
  dataset_id                  = "NORTHSTAR" 
  friendly_name               = "Database Northstar"
  description                 = "Dataset principale per l'importazione e analisi dati"
  location                    = "EU"
  delete_contents_on_destroy = false 
}

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
}

# CARICAMENTO FILE STATICI NEL BUCKET SPESE TRASPORTO
resource "google_storage_bucket_object" "file_statici_spese" {
  for_each = fileset("${path.module}/src/file_statici", "*")

  name   = each.value                                
  bucket = google_storage_bucket.spese_trasporto.name 
  source = "${path.module}/src/file_statici/${each.value}" 
}

resource "google_storage_bucket" "traduzione_immagini" {
  name                        = "bkt-traduzione-immagini"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "bucket_codice_funzioni" {
  name                        = "bkt-functions-code"
  location                    = "EU"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# --- CLOUD FUNCTIONS ---

#DRIVE TO GCP

data "archive_file" "zip_drive_to_gcp" {
  type        = "zip"
  source_dir  = "${path.module}/src/drive_to_gcp" 
  output_path = "${path.module}/src/drive_to_gcp.zip"
}

resource "google_storage_bucket_object" "upload_zip_drive_to_gcp" {
  name   = "drive_to_gcp_${data.archive_file.zip_drive_to_gcp.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_drive_to_gcp.output_path
}

resource "google_cloudfunctions2_function" "function_drive_to_gcp" {
  name        = "drive-to-gcp-fn"
  location    = "europe-west1" 
  description = "Importa dati da Google Drive a GCP"

  build_config {
    runtime     = "python311" 
    
    entry_point = "drive_to_gcp" 

    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
        object = google_storage_bucket_object.upload_zip_drive_to_gcp.name
      }
    }
  }

  service_config {
    min_instance_count               = 0
    max_instance_count               = 5
    available_memory                 = "1G"
    available_cpu                    = "1"
    timeout_seconds                  = 300
    max_instance_request_concurrency = 80
    service_account_email = google_service_account.cloud_worker.email
  }
}

#TABLES LOADING

data "archive_file" "zip_tables_loading" {
  type        = "zip"
  source_dir  = "${path.module}/src/tables_loading" 
  output_path = "${path.module}/src/tables_loading.zip"
}

resource "google_storage_bucket_object" "upload_zip_tables_loading" {
  name   = "tables_loading_${data.archive_file.zip_tables_loading.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_tables_loading.output_path
}

resource "google_cloudfunctions2_function" "function_tables_loading" {
  name        = "tables-loading-fn"
  location    = "europe-west1" 
  description = "Carica i dati importati da Drive in tabelle Big Query"

  build_config {
    runtime     = "python311" 
    
    entry_point = "run_sqlite_to_bigquery" 

    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
        object = google_storage_bucket_object.upload_zip_tables_loading.name
      }
    }
  }

  service_config {
    min_instance_count               = 0
    max_instance_count               = 3
    available_memory                 = "16G"
    available_cpu                    = "4"
    timeout_seconds                  = 3600
    max_instance_request_concurrency = 80
    service_account_email = google_service_account.cloud_worker.email
  }
}

#SPESE DI TRASPORTO

data "archive_file" "zip_calcolo_spese_trasporto" {
  type        = "zip"
  source_dir  = "${path.module}/src/calcolo_spese_trasporto" 
  output_path = "${path.module}/src/calcolo_spese_trasporto.zip"
}

resource "google_storage_bucket_object" "upload_zip_calcolo_spese_trasporto" {
  name   = "calcolo_spese_trasporto_${data.archive_file.zip_calcolo_spese_trasporto.output_md5}.zip"
  bucket = google_storage_bucket.bucket_codice_funzioni.name
  source = data.archive_file.zip_calcolo_spese_trasporto.output_path
}

resource "google_cloudfunctions2_function" "function_calcolo_spese_trasporto" {
  name        = "calcolo-spese-trasporto-fn"
  location    = "europe-west1"
  
  build_config {
    runtime     = "python311"
    entry_point = "elabora_spese_trasporto"      
    
    source {
      storage_source {
        bucket = google_storage_bucket.bucket_codice_funzioni.name
        object = google_storage_bucket_object.upload_zip_calcolo_spese_trasporto.name
      }
    }
  }

  service_config {
    max_instance_count               = 5
    max_instance_request_concurrency = 80
    available_memory                 = "1G" 
    available_cpu                    = "1" 
    timeout_seconds                  = 60
    service_account_email = google_service_account.cloud_worker.email
  }

  event_trigger {
    trigger_region        = "eu"
    event_type            = "google.cloud.storage.object.v1.finalized"
    service_account_email = google_service_account.cloud_worker.email
    
    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.spese_trasporto.name
    }
  }
}
resource "google_storage_bucket_iam_member" "eventarc_storage_permissions" {
  bucket = google_storage_bucket.spese_trasporto.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

data "google_project" "current" {}

resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = "cloud-platform-northstar"
  role    = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# --- PIANIFICAZIONE QUERY ---

# ANAGRAFICA PRODOTTI

resource "google_bigquery_data_transfer_config" "schedulazione_anagrafica_prodotti" {
  display_name           = "Query Anagrafica Prodotti"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 15:00"
  service_account_name   = google_service_account.cloud_worker.email

  params = {
    query = <<-EOF
      DECLARE base_img_url STRING DEFAULT 'https://marketplace.toctocshop.com/media/sincro/img/';
      DECLARE dynamic_uri STRING;
      DECLARE export_query STRING;

      -- 1. Creazione della tabella su BigQuery (i dati originali rimangono invariati)
      CREATE OR REPLACE TABLE DB_NORTHSTAR.ANAGRAFICA_PRODOTTO AS (

          WITH additional_attributes AS (
              SELECT sku,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'fornitore=%%' THEN SUBSTR(additional_attributes, 11) END) AS fornitore,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'ean=%%' THEN SUBSTR(additional_attributes, 5) END) AS ean,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'pdf=%%' THEN SUBSTR(additional_attributes, 5) END) AS pdf,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'genere=%%' THEN SUBSTR(additional_attributes, 8) END) AS genere,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'marca=%%' THEN SUBSTR(additional_attributes, 7) END) AS marca,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'costo=%%' THEN SUBSTR(additional_attributes, 7) END) AS costo,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'dimensioni=%%' THEN SUBSTR(additional_attributes, 12) END) AS dimensioni,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'dettagli=%%' THEN SUBSTR(additional_attributes, 10) END) AS dettagli,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'manufacturer=%%' THEN SUBSTR(additional_attributes, 14) END) AS manufacturer,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'tp_ds=%%' THEN SUBSTR(additional_attributes, 7) END) AS tp_ds,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'diametro_ruote=%%' THEN SUBSTR(additional_attributes, 16) END) AS diametro_ruote,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'ebay_it=%%' THEN SUBSTR(additional_attributes, 9) END) AS ebay_it,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'personaggio=%%' THEN SUBSTR(additional_attributes, 13) END) AS personaggio,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_it=%%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_it,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_fr=%%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_fr,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_de=%%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_de,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_gb=%%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_gb,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_es=%%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_es,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_it_sconto=%%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_it_sconto,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_fr_sconto=%%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_fr_sconto,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_gb_sconto=%%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_gb_sconto,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_de_sconto=%%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_de_sconto,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_es_sconto=%%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_es_sconto,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_it_special_to_date=%%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_it_special_to_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_fr_special_to_date=%%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_fr_special_to_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_de_special_to_date=%%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_de_special_to_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_es_special_to_date=%%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_es_special_to_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_gb_special_to_date=%%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_gb_special_to_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'special_to_date=%%' THEN SUBSTR(additional_attributes, 17) END) AS special_to_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'special_from_date=%%' THEN SUBSTR(additional_attributes, 19) END) AS special_from_date,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'tax_class_name=%%' THEN SUBSTR(additional_attributes, 16) END) AS iva,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'privalia_mktplace=%%' THEN SUBSTR(additional_attributes, 19) END) AS privalia_mktplace,
              MAX(CASE WHEN LOWER(additional_attributes) LIKE 'privalia_mktplace_raccomanded=%%' THEN SUBSTR(additional_attributes, 31) END) AS privalia_mktplace_raccomanded
              FROM DB_NORTHSTAR.dbo_m2_additional_attributes
              GROUP BY sku
          ),

          gallery AS (
              SELECT 
              sku,
              image_array[SAFE_OFFSET(0)] AS gallery_0,
              image_array[SAFE_OFFSET(1)] AS gallery_1,
              image_array[SAFE_OFFSET(2)] AS gallery_2,
              image_array[SAFE_OFFSET(3)] AS gallery_3,
              image_array[SAFE_OFFSET(4)] AS gallery_4,
              image_array[SAFE_OFFSET(5)] AS gallery_5,
              image_array[SAFE_OFFSET(6)] AS gallery_6,
              image_array[SAFE_OFFSET(7)] AS gallery_7,
              image_array[SAFE_OFFSET(8)] AS gallery_8,
              image_array[SAFE_OFFSET(9)] AS gallery_9
              FROM (
                  SELECT 
                      sku,
                      SPLIT(REPLACE(additional_images, '[path]', ''), ',') AS image_array
                  FROM `DB_NORTHSTAR.dbo_m2_articoli`
              )
          ),

          base_data AS (
              SELECT 
                  a.* EXCEPT(sku),
                  COALESCE(a.sku, b.sku) AS sku, 
                  b.name, b.product_type, b.categories, b.color, b.size, b.price, b.special_price, b.qty, b.description, b.short_description, b.parent,
                  LTRIM(REPLACE(b.thumbnail_image, '[path]', ''), '/') AS thumbnail_image, 
                  LTRIM(REPLACE(b.base_image, '[path]', ''), '/') AS base_image, 
                  LTRIM(REPLACE(b.small_image, '[path]', ''), '/') AS small_image,
                  LTRIM(ga.gallery_0, '/') AS gallery_0, 
                  LTRIM(ga.gallery_1, '/') AS gallery_1, 
                  LTRIM(ga.gallery_2, '/') AS gallery_2, 
                  LTRIM(ga.gallery_3, '/') AS gallery_3, 
                  LTRIM(ga.gallery_4, '/') AS gallery_4, 
                  LTRIM(ga.gallery_5, '/') AS gallery_5, 
                  LTRIM(ga.gallery_6, '/') AS gallery_6, 
                  LTRIM(ga.gallery_7, '/') AS gallery_7, 
                  LTRIM(ga.gallery_8, '/') AS gallery_8, 
                  LTRIM(ga.gallery_9, '/') AS gallery_9
              FROM additional_attributes a 
              FULL OUTER JOIN `DB_NORTHSTAR.dbo_m2_articoli` b ON a.sku = b.sku
              FULL OUTER JOIN gallery ga ON a.sku = ga.sku
          )

          SELECT 
              * EXCEPT(
                  thumbnail_image, base_image, small_image,
                  gallery_0, gallery_1, gallery_2, gallery_3, gallery_4, gallery_5, gallery_6, gallery_7, gallery_8, gallery_9
              ),
              
              -- base_image
              CASE WHEN NULLIF(base_image, '') IS NOT NULL AND base_image LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(base_image, '-')[SAFE_OFFSET(0)], '/', base_image) 
                  ELSE base_image END AS base_image,

              -- thumbnail_image
              CASE WHEN NULLIF(thumbnail_image, '') IS NOT NULL AND COALESCE(base_image, thumbnail_image) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, thumbnail_image), '-')[SAFE_OFFSET(0)], '/', thumbnail_image) 
                  ELSE thumbnail_image END AS thumbnail_image,
                  
              -- small_image
              CASE WHEN NULLIF(small_image, '') IS NOT NULL AND COALESCE(base_image, small_image) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, small_image), '-')[SAFE_OFFSET(0)], '/', small_image) 
                  ELSE small_image END AS small_image,
                  
              -- gallery_0 ... 9 ...
              CASE WHEN NULLIF(gallery_0, '') IS NOT NULL AND COALESCE(base_image, gallery_0) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_0), '-')[SAFE_OFFSET(0)], '/', gallery_0) 
                  ELSE gallery_0 END AS gallery_0,
                  
              CASE WHEN NULLIF(gallery_1, '') IS NOT NULL AND COALESCE(base_image, gallery_1) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_1), '-')[SAFE_OFFSET(0)], '/', gallery_1) 
                  ELSE gallery_1 END AS gallery_1,
                  
              CASE WHEN NULLIF(gallery_2, '') IS NOT NULL AND COALESCE(base_image, gallery_2) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_2), '-')[SAFE_OFFSET(0)], '/', gallery_2) 
                  ELSE gallery_2 END AS gallery_2,
                  
              CASE WHEN NULLIF(gallery_3, '') IS NOT NULL AND COALESCE(base_image, gallery_3) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_3), '-')[SAFE_OFFSET(0)], '/', gallery_3) 
                  ELSE gallery_3 END AS gallery_3,
                  
              CASE WHEN NULLIF(gallery_4, '') IS NOT NULL AND COALESCE(base_image, gallery_4) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_4), '-')[SAFE_OFFSET(0)], '/', gallery_4) 
                  ELSE gallery_4 END AS gallery_4,
                  
              CASE WHEN NULLIF(gallery_5, '') IS NOT NULL AND COALESCE(base_image, gallery_5) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_5), '-')[SAFE_OFFSET(0)], '/', gallery_5) 
                  ELSE gallery_5 END AS gallery_5,
                  
              CASE WHEN NULLIF(gallery_6, '') IS NOT NULL AND COALESCE(base_image, gallery_6) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_6), '-')[SAFE_OFFSET(0)], '/', gallery_6) 
                  ELSE gallery_6 END AS gallery_6,
                  
              CASE WHEN NULLIF(gallery_7, '') IS NOT NULL AND COALESCE(base_image, gallery_7) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_7), '-')[SAFE_OFFSET(0)], '/', gallery_7) 
                  ELSE gallery_7 END AS gallery_7,
                  
              CASE WHEN NULLIF(gallery_8, '') IS NOT NULL AND COALESCE(base_image, gallery_8) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_8), '-')[SAFE_OFFSET(0)], '/', gallery_8) 
                  ELSE gallery_8 END AS gallery_8,
                  
              CASE WHEN NULLIF(gallery_9, '') IS NOT NULL AND COALESCE(base_image, gallery_9) LIKE '%%-%%'
                  THEN CONCAT(base_img_url, SPLIT(COALESCE(base_image, gallery_9), '-')[SAFE_OFFSET(0)], '/', gallery_9) 
                  ELSE gallery_9 END AS gallery_9
                  
          FROM base_data
      );

      -- 2. Costruzione della stringa URI con la data corrente (Timezone Europa/Roma)
      SET dynamic_uri = CONCAT('gs://${google_storage_bucket.anagrafica_prodotti.name}/anagrafica_', CAST(CURRENT_DATE('Europe/Rome') AS STRING), '_*.csv');

      -- 3. Costruzione della query SQL dinamica per l'esportazione
      SET export_query = FORMAT("""
          EXPORT DATA OPTIONS(
            uri='%s',
            format='CSV',
            overwrite=true,
            header=true
          ) AS
          SELECT 
            * EXCEPT(
              costo, amazon_price_it, amazon_price_fr, amazon_price_de, amazon_price_gb, amazon_price_es, 
              amazon_price_it_sconto, amazon_price_fr_sconto, amazon_price_gb_sconto, amazon_price_de_sconto, amazon_price_es_sconto
            ),
            REPLACE(costo, '.', ',') AS costo,
            REPLACE(amazon_price_it, '.', ',') AS amazon_price_it,
            REPLACE(amazon_price_fr, '.', ',') AS amazon_price_fr,
            REPLACE(amazon_price_de, '.', ',') AS amazon_price_de,
            REPLACE(amazon_price_gb, '.', ',') AS amazon_price_gb,
            REPLACE(amazon_price_es, '.', ',') AS amazon_price_es,
            REPLACE(amazon_price_it_sconto, '.', ',') AS amazon_price_it_sconto,
            REPLACE(amazon_price_fr_sconto, '.', ',') AS amazon_price_fr_sconto,
            REPLACE(amazon_price_gb_sconto, '.', ',') AS amazon_price_gb_sconto,
            REPLACE(amazon_price_de_sconto, '.', ',') AS amazon_price_de_sconto,
            REPLACE(amazon_price_es_sconto, '.', ',') AS amazon_price_es_sconto
          FROM DB_NORTHSTAR.ANAGRAFICA_PRODOTTO;
      """, dynamic_uri);

      -- 4. Esecuzione della query di esportazione
      EXECUTE IMMEDIATE export_query;
    EOF
  }

  depends_on = [
    google_project_iam_member.cloud_worker_permissions,
    google_storage_bucket.anagrafica_prodotti
  ]
}

# REPORT FORNITORI

resource "google_bigquery_data_transfer_config" "schedulazione_report_fornitori" {
  display_name           = "Export Report Fornitori"
  location               = "EU"
  data_source_id         = "scheduled_query"
  schedule               = "every sunday 15:15" 
  service_account_name   = google_service_account.cloud_worker.email

  params = {
    query = <<-EOF
      DECLARE dest_uri STRING;
      -- Uso timezone Europe/Rome e sfuggo i % per Terraform (%%)
      SET dest_uri = CONCAT('gs://${google_storage_bucket.report_fornitori.name}/report_fornitori_', FORMAT_DATE('%%Y%%m%%d', CURRENT_DATE('Europe/Rome')), '_*.csv');

      -- 1. Creazione della tabella su BigQuery (i dati originali mantengono i formati numerici)
      CREATE OR REPLACE TABLE DB_NORTHSTAR.REPORT_FORNITORI AS ( 
        SELECT 
          sku, 
          fornitore, 
          costo, 
          iva, 
          nazione_des,
          pagamento_def,
          TRIM(MAX(name), '"') AS nome,
          -- Sfuggo i % per Terraform (%%)
          SAFE.PARSE_DATE('%%Y%%m%%d', SUBSTR(MAX(DATAISO), 1, 8)) AS data_spedizione,
          SUM(SAFE_CAST(REPLACE(prezzo_totale, ',', '.') AS FLOAT64)) AS prezzo_totale,
          sum(qta_spedita) as tot_qta_spedita,
          AVG(SAFE_CAST(REPLACE(PREZZO_UNITARIO, ',', '.') AS FLOAT64)) AS prezzo_unitario
        FROM (
          SELECT 
            o.sku, 
            p.name, 
            p.fornitore, 
            p.costo,
            o.qta_spedita, 
            o.ordine, 
            o.DATAISO, 
            t.newnew as pagamento_def, 
            o.PREZZO_UNITARIO, 
            o.PREZZO_TOTALE, 
            p.iva AS iva,
            t.NAZIONE_DES,
          FROM `DB_NORTHSTAR.dbo_ordini_righe` o 
          LEFT JOIN `DB_NORTHSTAR.ANAGRAFICA_PRODOTTO` p USING(sku)
          LEFT JOIN `DB_NORTHSTAR.dbo_ordini_testate_pag` t USING(ORDINE)
          WHERE o.DATA_SPEDIZIONE != "000000"
        )
        GROUP BY ALL
      );

      -- 2. Esportazione dinamica in CSV con sostituzione del punto in virgola
      EXECUTE IMMEDIATE FORMAT("""
        EXPORT DATA OPTIONS(
          uri='%%s',
          format='CSV',
          overwrite=true,
          header=true,
          field_delimiter=';'
        ) AS
        SELECT 
          * EXCEPT(prezzo_totale, tot_qta_spedita, prezzo_unitario),
          REPLACE(CAST(prezzo_totale AS STRING), '.', ',') AS prezzo_totale,
          REPLACE(CAST(tot_qta_spedita AS STRING), '.', ',') AS tot_qta_spedita,
          REPLACE(CAST(prezzo_unitario AS STRING), '.', ',') AS prezzo_unitario
        FROM `DB_NORTHSTAR.REPORT_FORNITORI`
      """, dest_uri);
    EOF
  }

  depends_on = [
    google_project_iam_member.cloud_worker_permissions,
    google_storage_bucket.report_fornitori
  ]
}

# --- SCHEDULAZIONI CLOUD FUNCTIONS ---

# DRIVE TO GCP
resource "google_cloud_scheduler_job" "schedulazione_drive_to_gcp" {
  name             = "drive-to-bq-scheduler"
  description      = "Schedulazione per caricare i dati da Drive a BigQuery ogni domenica"
  schedule         = "45 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = "europe-west1"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.function_drive_to_gcp.service_config[0].uri
    oidc_token {
      service_account_email = google_service_account.cloud_worker.email
    }
  }

  depends_on = [
    google_cloudfunctions2_function.function_drive_to_gcp,
    google_project_service.api_necessarie
  ]
}

# TABLES LOADING

resource "google_cloud_scheduler_job" "schedulazione_tables_loading" {
  name             = "tables-loading-scheduler"
  description      = "Schedulazione per creare le tabelle in BigQuery ogni domenica"
  schedule         = "55 16 * * 0"
  time_zone        = "Europe/Rome"
  region           = "europe-west1"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.function_tables_loading.service_config[0].uri
    oidc_token {
      service_account_email = google_service_account.cloud_worker.email
    }
  }

  depends_on = [
    google_cloudfunctions2_function.function_tables_loading,
    google_project_service.api_necessarie
  ]
}