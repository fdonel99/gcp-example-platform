import sys
import pysqlite3
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import sqlite3

import os
import io
import urllib.request
import urllib.parse
import zipfile
import gc
import shutil
from datetime import datetime, timezone
import functions_framework

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import bigquery
from google.cloud import storage
import polars as pl
import polars.selectors as cs 
import google.auth
import gspread

# --- CONFIGURAZIONE AMBIENTE ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', '')
DATASET_STORICO_ID = os.environ.get('DATASET_STORICO_ID', 'NORTHSTAR_STORICO')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SHEET_ID = os.environ.get('SHEET_ID', '1ptH6m4mS6UozgrtRUfoP_wMMwbx7wTiIn1T6eJ0Vy1c') 
MOUNT_PATH = '/mnt/bucket'
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]

def invia_notifica_telegram(messaggio):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configurato. Salto invio notifica.")
        return

    if 'prod' in PROJECT_ID.lower() or PROJECT_ID == 'cloud-platform-northstar':
        prefisso = "📚 *[PROD STORICO]* - "
    elif 'test' in PROJECT_ID.lower():
        prefisso = "🧪 *[TEST STORICO]* - "
    else:
        prefisso = "⚙️ *[INFO]* - "

    messaggio_formattato = f"{prefisso}{messaggio}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': messaggio_formattato, 'parse_mode': 'Markdown'}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"⚠️ Errore notifica Telegram: {e}")

@functions_framework.http
def run_load_storico(request):
    """
    Funzione manuale/una-tantum:
    - Scarica il file storico da Drive
    - Lo elabora con Polars e Sheets (Applicando RTRIM a tutti i campi di testo)
    - Lo carica in TRUNCATE nel Dataset Storico
    """
    request_json = request.get_json(silent=True) or {}
    
    folder_id = request_json.get('folder_id') or os.environ.get('FOLDER_ID')
    target_filename = request_json.get('file_name', '2023-2024-2025.zip')
    
    if not folder_id:
        msg = "Parametro 'folder_id' mancante. Forniscilo nel JSON o nel Terraform."
        invia_notifica_telegram(f"🚨 *Errore!*\n{msg}")
        return f"Errore: {msg}", 400
    
    local_zip_path = '/tmp/storico.zip'
    extract_to = '/tmp/extracted_storico/'
    
    try:
        invia_notifica_telegram(f"Inizio elaborazione file storico `{target_filename}`...")
        credentials, project = google.auth.default(scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=credentials)
        bq_client = bigquery.Client(project=PROJECT_ID)

        print(f"Cerco '{target_filename}' nella cartella {folder_id}...")
        query = f"'{folder_id}' in parents and name = '{target_filename}' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = results.get('files', [])
        
        if not files:
            msg = f"File '{target_filename}' non trovato su Drive."
            invia_notifica_telegram(f"❌ {msg}")
            return msg, 404
            
        file_id = files[0]['id']
        print(f"Trovato! ID: {file_id}. Avvio download (potrebbe volerci tempo)...")

        drive_request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
        with open(local_zip_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, drive_request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"Download: {int(status.progress() * 100)}%")

        print("Estrazione in corso...")
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)
        os.makedirs(extract_to, exist_ok=True)

        with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

        sqlite_files = [f for f in os.listdir(extract_to) if f.endswith('.sqlite')]
        if not sqlite_files:
            raise ValueError("Il file ZIP non contiene un database `.sqlite`.")
        
        sqlite_path = os.path.join(extract_to, sqlite_files[0])
        print(f"Database trovato: {sqlite_path}")

        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        sqlite_uri = f"sqlite:///{sqlite_path.lstrip('/')}"

        gc_sheets = gspread.authorize(credentials)
        sh = gc_sheets.open_by_key(SHEET_ID)
        
        ws_mov = sh.worksheet('MOVIMENTO')
        df_mov = pl.DataFrame(ws_mov.get_all_records()).select(["MOVIMENTO", "DESCRIZIONE_MOVIMENTO", "CLASSIFICAZIONE"]).unique(subset=["MOVIMENTO"])
        
        ws_tipo = sh.worksheet('TIPO')
        df_tipo = pl.DataFrame(ws_tipo.get_all_records()).select(["TIPO", "DESCRIZIONE_TIPO"]).unique(subset=["TIPO"])

        # Eseguo RTRIM anche sui fogli di supporto per evitare mancati match!
        df_mov = df_mov.with_columns(cs.string().str.strip_chars())
        df_tipo = df_tipo.with_columns(cs.string().str.strip_chars())
        
        df_mov = df_mov.with_columns(pl.col("MOVIMENTO").cast(pl.Utf8))
        df_tipo = df_tipo.with_columns(pl.col("TIPO").cast(pl.Utf8))

        bq_jobs = []
        parquets_da_eliminare = []

        for t_name in tables:
            try:
                clean_table_name = t_name.replace(' ', '_').replace('-', '_')
                table_id = f"{PROJECT_ID}.{DATASET_STORICO_ID}.{clean_table_name}"
                
                parquet_filename = f"{clean_table_name}_storico.parquet"
                parquet_path = os.path.join(MOUNT_PATH, parquet_filename)
                gcs_uri = f"gs://{BUCKET_NAME}/{parquet_filename}"
                
                print(f"Elaborazione tabella {t_name}...")
                query = f"SELECT * FROM {t_name}"
                df = pl.read_database_uri(query=query, uri=sqlite_uri)
            
                df = df.with_columns(cs.string().str.strip_chars())
                
                if t_name == "dbo_movimenti":
                    if "SKU" in df.columns:
                        df = df.with_columns(pl.col("SKU").str.replace_all(" ", "", literal=True))
                    
                    df = df.with_columns([pl.col("MOVIMENTO").cast(pl.Utf8), pl.col("TIPO").cast(pl.Utf8)])
                    df = df.join(df_mov, on="MOVIMENTO", how="left").join(df_tipo, on="TIPO", how="left")

                df.write_parquet(parquet_path)
                del df
                gc.collect()

                print(f"Avvio caricamento su BQ in TRUNCATE ({table_id})...")
                job_config = bigquery.LoadJobConfig(
                    source_format=bigquery.SourceFormat.PARQUET,
                    write_disposition="WRITE_TRUNCATE", 
                )
                job = bq_client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
                bq_jobs.append((t_name, job))
                parquets_da_eliminare.append(parquet_path)
                
            except Exception as table_error:
                print(f"❌ Errore durante l'elaborazione della tabella {t_name}: {table_error}")
                if 'df' in locals():
                    del df
                    gc.collect()

        print("Attesa completamento job BigQuery in parallelo...")
        for t_name, job in bq_jobs:
            try:
                job.result()
                print(f"✅ Storico caricato in: {t_name}")
            except Exception as e:
                print(f"❌ Errore BQ per {t_name}: {e}")

        print("Svuotamento GCS e disco locale...")
        for p_path in parquets_da_eliminare:
            if os.path.exists(p_path): os.remove(p_path)
        
        shutil.rmtree(extract_to, ignore_errors=True)
        if os.path.exists(local_zip_path):
            os.remove(local_zip_path)

        invia_notifica_telegram(f"✅ *Caricamento Storico Completato!*\nIl file `{target_filename}` è stato elaborato (con pulizia degli spazi in eccesso) e salvato nel dataset `{DATASET_STORICO_ID}`.")
        
        return "Caricamento storico completato con successo", 200

    except Exception as e:
        errore_msg = str(e)
        print(f"❌ Errore: {errore_msg}")
        if os.path.exists(extract_to): shutil.rmtree(extract_to, ignore_errors=True)
        if os.path.exists(local_zip_path): os.remove(local_zip_path)
        
        invia_notifica_telegram(f"🚨 *Errore Caricamento Storico*\nDettaglio:\n`{errore_msg}`")
        return f"Errore interno: {errore_msg}", 500