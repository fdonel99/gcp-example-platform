output "dataset_principale_id" {
  description = "L'ID del dataset BigQuery principale"
  value       = google_bigquery_dataset.dataset_principale.dataset_id
}

output "bucket_anagrafica_prodotti_name" {
  description = "Nome del bucket per l'anagrafica prodotti"
  value       = google_storage_bucket.anagrafica_prodotti.name
}

output "bucket_report_fornitori_name" {
  description = "Nome del bucket per il report fornitori"
  value       = google_storage_bucket.report_fornitori.name
}

output "bucket_codice_funzioni_name" {
  description = "Nome del bucket che ospita il codice delle Cloud Functions"
  value       = google_storage_bucket.bucket_codice_funzioni.name
}

output "bucket_spese_trasporto_name" {
  description = "Nome del bucket per le spese di trasporto"
  value       = google_storage_bucket.spese_trasporto.name
}

output "bucket_export_ns_zip_name" {
  value = google_storage_bucket.export_ns_zip.name
}
output "bucket_infografica_input_name" {
  value = google_storage_bucket.infografica_input.name
}
output "bucket_infografica_output_name" {
  value = google_storage_bucket.infografica_output.name
}

output "bucket_listino_costi_trasporto_name" {
  description = "Il nome del bucket di input per le tariffe"
  value       = google_storage_bucket.bucket_listino_costi_trasporto.name
}