# ==========================================
# GESTIONE GOOGLE DOCUMENT AI
# ==========================================

# 1. Abilitiamo l'API di Document AI (se non è già attiva)
resource "google_project_service" "documentai" {
  project = var.project_id
  service = "documentai.googleapis.com"
  
  disable_on_destroy = false
}

# 2. Creiamo il Processore OCR
resource "google_document_ai_processor" "ocr_processor" {
  project      = var.project_id
  location     = "eu"
  
  # Usa la tua stessa logica elegante per il nome visualizzato nella console GCP
  display_name = "OCR Infografiche - ${title(var.environment)}"
  
  type         = "OCR_PROCESSOR" 
  
  depends_on = [
    google_project_service.documentai
  ]
}

# 3. Output per recuperare l'ID univoco generato da GCP
output "document_ai_processor_id" {
  value       = google_document_ai_processor.ocr_processor.id
  description = "L'ID univoco del processore Document AI (${var.environment})"
}