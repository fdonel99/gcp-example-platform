resource "google_secret_manager_secret" "telegram_token" {
  secret_id = "telegram-token-${var.environment}" 
  project   = var.project_id

  labels = {
    scopo = "secret-telegram-token"
  }
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "telegram_token_version" {
  secret      = google_secret_manager_secret.telegram_token.id
  secret_data = var.telegram_token_value
}

resource "google_secret_manager_secret_iam_member" "worker_telegram_secret_accessor" {
  secret_id = google_secret_manager_secret.telegram_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_worker.email}"
  project   = google_secret_manager_secret.telegram_chat_id.project
}

resource "google_secret_manager_secret" "telegram_chat_id" {
  secret_id = "telegram-chat-id-${var.environment}" 
  project   = var.project_id

  labels = {
    scopo = "secret-telegram-chat-id"
  }
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "telegram_chat_id_version" {
  secret      = google_secret_manager_secret.telegram_chat_id.id
  secret_data = var.telegram_chat_id_value
}

resource "google_secret_manager_secret_iam_member" "worker_telegram_chat_id_accessor" {
  secret_id = google_secret_manager_secret.telegram_chat_id.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_worker.email}"
  project   = google_secret_manager_secret.telegram_chat_id.project
}