# --- GESTIONE API ---

locals {
  gcp_services = [
"agentregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "analyticshub.googleapis.com",
    "apphub.googleapis.com",
    "apptopology.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "bigquerydatapolicy.googleapis.com",
    "bigquerydatatransfer.googleapis.com",
    "bigquerymigration.googleapis.com",
    "bigqueryreservation.googleapis.com",
    "bigquerystorage.googleapis.com",
    "cloudapiregistry.googleapis.com",
    "cloudapis.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtrace.googleapis.com",
    "compute.googleapis.com",
    "containerregistry.googleapis.com",
    "dataform.googleapis.com",
    "dataplex.googleapis.com",
    "datastore.googleapis.com",
    "drive.googleapis.com",
    "edgecache.googleapis.com",
    "eventarc.googleapis.com",
    "iam.googleapis.com",
    "iamconnectorcredentials.googleapis.com",
    "iamconnectors.googleapis.com",
    "iamcredentials.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "modelarmor.googleapis.com",
    "monitoring.googleapis.com",
    "networksecurity.googleapis.com",
    "networkservices.googleapis.com",
    "notebooks.googleapis.com",
    "observability.googleapis.com",
    "oslogin.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "saasservicemgmt.googleapis.com",
    "securitycenter.googleapis.com",
    "securitycentermanagement.googleapis.com",
    "servicemanagement.googleapis.com",
    "serviceusage.googleapis.com",
    "source.googleapis.com",
    "sql-component.googleapis.com",
    "storage-api.googleapis.com",
    "storage-component.googleapis.com",
    "storage.googleapis.com",
    "telemetry.googleapis.com",
    "texttospeech.googleapis.com",
    "translate.googleapis.com",
    "vision.googleapis.com" 
  ]
}

resource "google_project_service" "api_necessarie" {
  for_each           = toset(local.gcp_services)
  project            = "cloud-platform-northstar"
  service            = each.value
  disable_on_destroy = false # Evita di spegnere le API se distruggi le risorse in futuro
}