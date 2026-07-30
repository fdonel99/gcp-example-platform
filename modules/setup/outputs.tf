output "cloud_worker_sa_email" {
  description = "L'email del Service Account Worker"
  value       = google_service_account.cloud_worker.email
}