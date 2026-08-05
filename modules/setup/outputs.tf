output "cloud_worker_sa_email" {
  description = "L'email del Service Account Worker"
  value       = google_service_account.cloud_worker.email
}
output "cloud_worker_email" {
  description = "L'email del Service Account cloud_worker"
  value       = google_service_account.cloud_worker.email
}

output "telegram_secret_name" {
  description = "Nome del secret di Secret Manager per il token Telegram"
  value       = google_secret_manager_secret.telegram_token.secret_id
}

output "bq_scheduler_sa_email" {
  description = "L'email del Service Account dedicato alle Query Schedulate"
  value       = google_service_account.bq_scheduler.email
}

output "cf_scheduler_sa_email" {
  description = "L'email del Service Account dedicato a Cloud Scheduler"
  value       = google_service_account.cf_scheduler.email
}

output "telegram_chat_id_secret_name" {
  description = "Nome del secret per la Chat ID Telegram"
  value       = google_secret_manager_secret.telegram_chat_id.secret_id
}