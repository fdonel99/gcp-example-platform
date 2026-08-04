output "cloud_worker_sa_email" {
  description = "L'email del Service Account Worker"
  value       = google_service_account.cloud_worker.email
}

output "bq_scheduler_sa_email" {
  description = "L'email del Service Account dedicato alle Query Schedulate"
  value       = google_service_account.bq_scheduler.email
}

output "cf_scheduler_sa_email" {
  description = "L'email del Service Account dedicato a Cloud Scheduler"
  value       = google_service_account.cf_scheduler.email
}