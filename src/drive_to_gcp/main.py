import os
import io
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone  # <-- NUOVI IMPORT AGGIUNTI
import functions_framework
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage
import google.auth

# --- CONFIGURAZIONE TELEGRAM ---
TELEGRAM_TOKEN = '8906093462:AAFi_3hQum83NXR7dMYLu0RZXKDLvJwdGro'
TELEGRAM_CHAT_ID = '5122727806'

def invia_notifica_telegram(messaggio):
    """Invia un messaggio di testo tramite il bot Telegram."""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'INSERISCI_QUI_IL_TUO_TOKEN':
        print("Telegram non configurato. Salto invio notifica.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TELEGRAM_CHAT_ID, 
        'text': messaggio,
        'parse_mode': 'Markdown'
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
        print("✅ Notifica Telegram inviata con successo!")
    except Exception as e:
        print(f"⚠️ Errore durante l'invio della notifica Telegram: {e}")

# Scope necessari per accedere a Google Drive in sola lettura
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
    
    folder_id = request_json['folder_id']
    bucket_name = request_json.get('bucket_name', 'bkt-export-ns-zip') 
    
    try:
        # 1. Autenticazione automatica tramite il Service Account
        credentials, project = google.auth.default(scopes=SCOPES)
        
        # Inizializzazione dei client
        drive_service = build('drive', 'v3', credentials=credentials)
        storage_client = storage.Client(project=project)
        
        print(f"Recupero della lista dei file dalla cartella Drive: {folder_id}...")
        
        # Query per cercare i file nella cartella che non sono nel cestino
        query = f"'{folder_id}' in parents and trashed = false"
        
        # Parametri per supportare i Drive Condivisi ed elementi condivisi esterni
        # ---> AGGIUNTO 'createdTime' ai fields richiesti <---
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
        
        # 2. Ordinamento dei file per nome (alfabetico)
        files.sort(key=lambda x: x['name'].lower())
        
        # 3. Selezione dell'ultimo file
        target_file = files[-1]
        file_id = target_file['id']
        original_name = target_file['name']
        mime_type = target_file.get('mimeType')
        created_time_str = target_file.get('createdTime')  # Recupero la data di creazione
        
        print(f"File selezionato: {original_name} (ID: {file_id}, Creato il: {created_time_str})")

        # ---> INIZIO CONTROLLO DEI 7 GIORNI <---
        if created_time_str:
            # L'API di Drive restituisce la data nel formato '2023-10-25T10:00:00.000Z'
            # La sostituzione di 'Z' con '+00:00' garantisce compatibilità anche con versioni Python meno recenti
            file_date = datetime.fromisoformat(created_time_str.replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            
            # Calcolo la differenza di tempo
            if (now_utc - file_date) > timedelta(days=6):
                messaggio_blocco = "Estrazione da Drive non eseguita. Nessun file caricato negli ultimi 6 giorni"
                print(messaggio_blocco)
                invia_notifica_telegram(messaggio_blocco)
                return {
                    "status": "saltato",
                    "messaggio": messaggio_blocco
                }, 200
        # ---> FINE CONTROLLO DEI 6 GIORNI <---
        
        # Determina il nome di destinazione nel bucket
        destination_blob_name = request_json.get('destination_name', original_name)
        
        # 4. Controllo esistenza su GCS prima del download
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        
        print(f"Verifica esistenza di '{destination_blob_name}' nel bucket '{bucket_name}'...")
        if blob.exists():
            print(f"⚠️ Il file '{destination_blob_name}' è già presente. Operazione saltata.")
            
            # ---> NOTIFICA TELEGRAM: FILE GIA' PRESENTE <---
            invia_notifica_telegram(f"⏩ *Nessuna azione necessaria*\nIl file `{destination_blob_name}` non è stato prelevato perché risulta già presente nel bucket Cloud Storage `{bucket_name}`.")
            
            return {
                "status": "saltato",
                "file_selezionato": original_name,
                "messaggio": "File già presente su GCS."
            }, 200
        
        # 5. Download del file da Drive in memoria
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
        
        # 6. Upload su Cloud Storage
        print(f"Caricamento su GCS in '{bucket_name}' come '{destination_blob_name}'...")
        blob.upload_from_file(file_buffer, content_type=mime_type)
        
        print("✅ Operazione completata con successo!")
        
        # ---> NOTIFICA TELEGRAM: SUCCESSO <---
        invia_notifica_telegram(f"✅ *Nuovo file prelevato!*\nIl file `{original_name}` è stato correttamente scaricato da Google Drive e salvato nel bucket `{bucket_name}`.")
        
        return {
            "status": "successo",
            "file_selezionato": original_name,
            "messaggio": f"Caricamento completato."
        }, 200

    except Exception as e:
        errore_msg = str(e)
        print(f"❌ Errore durante l'elaborazione: {errore_msg}")
        
        # ---> NOTIFICA TELEGRAM: ERRORE <---
        invia_notifica_telegram(f"🚨 *Errore Critico (Drive ➡️ GCS)*\nLa funzione si è interrotta a causa di un errore imprevisto.\n\n*Dettaglio:*\n`{errore_msg}`")
        
        return {"status": "errore", "messaggio": errore_msg}, 500