output "function_drive_to_gcp_uri" {
  description = "L'URI della Cloud Function Drive to GCP"
  value       = google_cloudfunctions2_function.function_drive_to_gcp.service_config[0].uri
}

output "function_tables_loading_uri" {
  description = "L'URI della Cloud Function Tables Loading"
  value       = google_cloudfunctions2_function.function_tables_loading.service_config[0].uri
}

output "function_anagrafica_prodotto_uri" {
  description = "L'URI della Cloud Function Anagrafica Prodotto"
  value       = google_cloudfunctions2_function.function_anagrafica_prodotto.service_config[0].uri
}