import os
import io
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
import functions_framework
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage
import google.auth

# --- CONFIGURAZIONE TELEGRAM E AMBIENTE ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', '')

def invia_notifica_telegram(messaggio):
    """Invia un messaggio di testo tramite il bot Telegram con prefisso ambiente."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configurato (Token o Chat ID mancanti). Salto invio notifica.")
        return

    if 'prod' in PROJECT_ID.lower() or PROJECT_ID == 'cloud-platform-northstar':
        prefisso = "🚀 *[PROD]* - "
    elif 'test' in PROJECT_ID.lower():
        prefisso = "🧪 *[TEST]* - "
    else:
        prefisso = "⚙️ *[INFO]* - "

    messaggio_formattato = f"{prefisso}{messaggio}"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TELEGRAM_CHAT_ID, 
        'text': messaggio_formattato,
        'parse_mode': 'Markdown'
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
        print(f"✅ Notifica Telegram inviata con successo per l'ambiente {prefisso.strip(' *[-]')}")
    except Exception as e:
        print(f"⚠️ Errore durante l'invio della notifica Telegram: {e}")

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

@functions_framework.http
def drive_to_gcp(request):
    """
    Cloud Function che elenca i file di una cartella Drive (anche Condivisa),
    li ordina per nome, prende l'ultimo e lo carica su GCS (se caricato negli ultimi 6 giorni).
    Invia notifiche Telegram in base all'esito.
    """
    request_json = request.get_json(silent=True)
    if request_json is None:
        request_json = {}
    
    if 'folder_id' not in request_json:
        errore_msg = "Parametro 'folder_id' mancante nel body JSON."
        invia_notifica_telegram(f"🚨 *Errore Cloud Function!*\n{errore_msg}")
        return f"Errore: {errore_msg}", 400

    if 'bucket_name' not in request_json:
        errore_msg = "Parametro 'bucket_name' mancante nel body JSON. Aggiornare Cloud Scheduler."
        invia_notifica_telegram(f"🚨 *Errore Cloud Function!*\n{errore_msg}")
        return f"Errore: {errore_msg}", 400
    
    folder_id = request_json['folder_id']
    bucket_name = request_json['bucket_name']
    
    try:
        # 1. Autenticazione tramite il Service Account
        credentials, project = google.auth.default(scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=credentials)
        storage_client = storage.Client(project=project)
        
        print(f"Recupero della lista dei file dalla cartella Drive: {folder_id}...")
        
        query = f"'{folder_id}' in parents and trashed = false"
        
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, mimeType, createdTime)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print(f"⚠️ Nessun file trovato nella cartella Drive con ID: {folder_id}")
            invia_notifica_telegram("🚨 *Errore Cloud Function!*\nNessun file trovato nella cartella indicata. Verifica la condivisione con il Service Account.")
            return f"Nessun file trovato.", 404
        
        files.sort(key=lambda x: x['name'].lower())
        
        target_file = files[-1]
        file_id = target_file['id']
        original_name = target_file['name']
        mime_type = target_file.get('mimeType')
        created_time_str = target_file.get('createdTime')
        
        print(f"File selezionato: {original_name} (ID: {file_id}, Creato il: {created_time_str})")

        if created_time_str:
            file_date = datetime.fromisoformat(created_time_str.replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            
            if (now_utc - file_date) > timedelta(days=6):
                messaggio_blocco = "Estrazione da Drive non eseguita. Nessun file caricato negli ultimi 6 giorni"
                print(messaggio_blocco)
                invia_notifica_telegram(messaggio_blocco)
                return {
                    "status": "saltato",
                    "messaggio": messaggio_blocco
                }, 200
        
        destination_blob_name = "export_latest.zip"
        
        print(f"Download di '{original_name}' da Google Drive...")
        
        drive_request = drive_service.files().get_media(
            fileId=file_id,
            supportsAllDrives=True
        )
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, drive_request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Progresso download: {int(status.progress() * 100)}%")
                
        file_buffer.seek(0)
        print("Download completato.")
        
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        print(f"Caricamento su GCS in '{bucket_name}' come '{destination_blob_name}'...")
        blob.upload_from_file(file_buffer, content_type=mime_type)
        
        print("✅ Operazione completata con successo!")
        invia_notifica_telegram(f"✅ *Nuovo file prelevato!*\nIl file `{original_name}` è stato correttamente scaricato da Google Drive e salvato nel bucket `{bucket_name}`.")
        
        return {
            "status": "successo",
            "file_selezionato": original_name,
            "messaggio": f"Caricamento completato."
        }, 200

    except Exception as e:
        errore_msg = str(e)
        print(f"❌ Errore durante l'elaborazione: {errore_msg}")
        invia_notifica_telegram(f"🚨 *Errore Critico (Drive ➡️ GCS)*\nLa funzione si è interrotta a causa di un errore imprevisto.\n\n*Dettaglio:*\n`{errore_msg}`")
        return {"status": "errore", "messaggio": errore_msg}, 500