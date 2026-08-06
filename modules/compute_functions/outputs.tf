output "function_drive_to_gcp_uri" {
  description = "L'URI della Cloud Function Drive to GCP"
  value       = google_cloudfunctions2_function.function_drive_to_gcp.service_config[0].uri
}

output "function_tables_loading_uri" {
  description = "L'URI della Cloud Function Tables Loading"
  value       = google_cloudfunctions2_function.function_tables_loading.service_config[0].uri
}

output "function_anagrafica_prodotto_uri" {
  description = "L'URI della Cloud Function BQ to Drive"
  value       = google_cloudfunctions2_function.function_bq_to_drive.service_config[0].uri
}