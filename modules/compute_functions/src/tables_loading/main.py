import sys
import pysqlite3
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import sqlite3

# Import standard
import os
import glob
import zipfile
import urllib.request
import urllib.parse
import gc
import shutil
from datetime import datetime, timedelta, timezone
import functions_framework

# Import Cloud e Dati
from google.cloud import bigquery
import polars as pl
import google.auth
import gspread

# --- CONFIGURAZIONE TELEGRAM E AMBIENTE ---
# I segreti ora vengono letti ESCLUSIVAMENTE dalle variabili d'ambiente (Secret Manager)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# GOOGLE_CLOUD_PROJECT è iniettato in automatico da Cloud Functions
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', '')

# Anche queste configurazioni ora dipendono dalle variabili passate da Terraform
DATASET_ID = os.environ.get('DATASET_ID')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
SHEET_ID = os.environ.get('SHEET_ID', '1ptH6m4mS6UozgrtRUfoP_wMMwbx7wTiIn1T6eJ0Vy1c') # Consigliato passare anche questo via TF

MOUNT_PATH = '/mnt/bucket'    # Percorso GCS Fuse fisso

def invia_notifica_telegram(messaggio):
    """Invia un messaggio di testo tramite il bot Telegram con prefisso ambiente."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configurato (Token o Chat ID mancanti). Salto invio notifica.")
        return

    # Determina il prefisso dinamico leggendo il nome del progetto
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


@functions_framework.http
def run_sqlite_to_bigquery(request):
    """
    Attivata via HTTP da Cloud Scheduler (Cron). 
    Cerca l'ultimo ZIP (se inserito negli ultimi 7 giorni), estrae e seleziona 
    SOLO il file SQLite corrispondente, lo elabora in parallelo su BigQuery e pulisce la RAM.
    """
    if not DATASET_ID or not BUCKET_NAME:
        errore_msg = "Parametri DATASET_ID o BUCKET_NAME mancanti nelle variabili d'ambiente."
        invia_notifica_telegram(f"🚨 *Errore Cloud Function!*\n{errore_msg}")
        return f"Errore: {errore_msg}", 400

    zip_path = os.path.join(MOUNT_PATH, 'export_latest.zip')
    file_name = 'export_latest.zip'
    
    if not os.path.exists(zip_path):
        msg_blocco = "Tabelle non aggiornate. File export_latest.zip non trovato sul bucket."
        print(msg_blocco)
        invia_notifica_telegram(msg_blocco)
        return msg_blocco, 200

    file_timestamp = os.path.getctime(zip_path)
    file_date = datetime.fromtimestamp(file_timestamp, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    
    marker_path = os.path.join(MOUNT_PATH, 'marker_elaborato.txt')
    if os.path.exists(marker_path):
        with open(marker_path, 'r') as f:
            content = f.read().strip()
            last_processed_ts = float(content) if content else 0.0
        
        if file_timestamp <= last_processed_ts:
            print(f"Nessun nuovo file da elaborare. {file_name} già processato in precedenza.")
            return "File già elaborato", 200

    if (now_utc - file_date) > timedelta(days=6):
        msg_blocco = "Tabelle non aggiornate. Nessun file inserito sul bucket negli ultimi 7 giorni"
        print(f"L'ultimo file '{file_name}' è del {file_date.strftime('%Y-%m-%d %H:%M:%S')}. {msg_blocco}")
        invia_notifica_telegram(msg_blocco)
        return msg_blocco, 200

    extract_to = '/tmp/extracted/'
    print(f"Cron avviato. Inizio elaborazione del file recente: '{file_name}'")

    try:
        bq_client = bigquery.Client(project=PROJECT_ID)

        if not os.path.exists(extract_to):
            os.makedirs(extract_to)

        print(f"Estrazione del file {zip_path} in corso...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print("Estrazione completata.")

        sqlite_files = [f for f in os.listdir(extract_to) if f.endswith('.sqlite')]
        if not sqlite_files:
            errore_msg = "Il file ZIP estratto non contiene file `.sqlite`."
            shutil.rmtree(extract_to, ignore_errors=True)
            print(f"Errore: {errore_msg}")
            invia_notifica_telegram(f"❌ *Errore:* {errore_msg}")
            return errore_msg, 400
        
        sqlite_path = os.path.join(extract_to, sqlite_files[0])

        print(f"File SQLite selezionato per l'elaborazione: {os.path.basename(sqlite_path)}")

        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tabelle trovate nel database: {tables}")
        conn.close() 

        sqlite_uri = f"sqlite:///{sqlite_path.lstrip('/')}"

        bq_jobs = []
        parquets_da_eliminare = []

        for t_name in tables:
            try:
                clean_table_name = t_name.replace(' ', '_').replace('-', '_')
                table_id = f"{PROJECT_ID}.{DATASET_ID}.{clean_table_name}"
                
                parquet_filename = f"{clean_table_name}_temp.parquet"
                parquet_path = os.path.join(MOUNT_PATH, parquet_filename)
                gcs_uri = f"gs://{BUCKET_NAME}/{parquet_filename}"
                
                print(f"Lettura tabella {t_name} ed esportazione in Parquet su GCS...")
                query = f"SELECT * FROM {t_name}"
                
                df = pl.read_database_uri(query=query, uri=sqlite_uri)
                
                if t_name == "dbo_movimenti":
                    print("Applicazione regole custom e arricchimento dati per dbo_movimenti...")
                    
                    if "SKU" in df.columns:
                        df = df.with_columns(pl.col("SKU").str.replace_all(" ", "", literal=True))
                    
                    print("Connessione a Google Sheets per Left Join...")
                    credentials, _ = google.auth.default(scopes=[
                        'https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly'
                    ])
                    gc_sheets = gspread.authorize(credentials)
                    
                    sh = gc_sheets.open_by_key(SHEET_ID)
                    
                    ws_mov = sh.worksheet('MOVIMENTO')
                    df_mov = pl.DataFrame(ws_mov.get_all_records())
                    df_mov = df_mov.select(["MOVIMENTO", "DESCRIZIONE MOVIMENTO", "CLASSIFICAZIONE"]).unique(subset=["MOVIMENTO"])
                    
                    ws_tipo = sh.worksheet('TIPO')
                    df_tipo = pl.DataFrame(ws_tipo.get_all_records())
                    df_tipo = df_tipo.select(["TIPO", "DESCRIZIONE TIPO"]).unique(subset=["TIPO"])
                    
                    df = df.with_columns([
                        pl.col("MOVIMENTO").cast(pl.Utf8),
                        pl.col("TIPO").cast(pl.Utf8)
                    ])
                    df_mov = df_mov.with_columns(pl.col("MOVIMENTO").cast(pl.Utf8))
                    df_tipo = df_tipo.with_columns(pl.col("TIPO").cast(pl.Utf8))
                    
                    df = df.join(df_mov, on="MOVIMENTO", how="left")
                    df = df.join(df_tipo, on="TIPO", how="left")
                    
                    print("Arricchimento completato con successo.")

                df.write_parquet(parquet_path)
                
                del df 
                gc.collect()
                
                print(f"Avvio job asincrono su BigQuery per {t_name}...")
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

        print("Tutti i dati estratti. Attesa che BigQuery completi i caricamenti in parallelo...")
        for t_name, job in bq_jobs:
            try:
                job.result()
                print(f"✅ Tabella confermata: {t_name}")
            except Exception as e:
                print(f"❌ Errore segnalato da BigQuery per {t_name}: {e}")

        print("Rimozione dei file Parquet temporanei dal bucket...")
        for p_path in parquets_da_eliminare:
            if os.path.exists(p_path):
                os.remove(p_path)

        print("Svuotamento RAM: rimozione dell'intera cartella estratta...")
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)

        with open(marker_path, 'w') as f:
            f.write(str(file_timestamp))
        print("Marker di elaborazione aggiornato. File originale lasciato intatto.")

        print("Processo completato con successo.")
        invia_notifica_telegram(f"✅ *Sincronizzazione Completata!*\nTutti i dati di `{file_name}` sono stati caricati su BigQuery.")
        
        return "Elaborazione completata con successo", 200
        
    except Exception as e:
        print(f"❌ Errore critico nel processo generale: {e}")
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)
            
        invia_notifica_telegram(f"🚨 *Errore Critico (CRON)*\nL'automazione si è interrotta sul file `{file_name}`.\n\nDettaglio errore:\n`{str(e)}`")
        return f"Errore interno: {e}", 500