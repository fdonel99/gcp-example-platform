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

# --- CONFIGURAZIONE TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8906093462:AAFi_3hQum83NXR7dMYLu0RZXKDLvJwdGro')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5122727806')

# --- CONFIGURAZIONE CLOUD (Dinamica tramite Variabili d'Ambiente) ---
PROJECT_ID = os.environ.get('PROJECT_ID', 'cloud-platform-northstar')
DATASET_ID = os.environ.get('DATASET_ID', 'NORTHSTAR')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'bkt-export-ns-zip')
MOUNT_PATH = '/mnt/bucket'    # Percorso GCS Fuse fisso

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


@functions_framework.http
def run_sqlite_to_bigquery(request):
    """
    Attivata via HTTP da Cloud Scheduler (Cron). 
    Cerca l'ultimo ZIP (se inserito negli ultimi 7 giorni), estrae e seleziona 
    SOLO il file SQLite corrispondente, lo elabora in parallelo su BigQuery e pulisce la RAM.
    """
    # 1. CERCA IL FILE DA ELABORARE
    list_of_files = glob.glob(os.path.join(MOUNT_PATH, '*.zip'))
    
    if not list_of_files:
        msg_blocco = "Tabelle non aggiornate. Nessun file inserito sul bucket negli ultimi 7 giorni"
        print(msg_blocco)
        invia_notifica_telegram(msg_blocco)
        return msg_blocco, 200

    zip_path = max(list_of_files, key=os.path.getctime)
    file_name = os.path.basename(zip_path)
    
    file_timestamp = os.path.getctime(zip_path)
    file_date = datetime.fromtimestamp(file_timestamp, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    
    if (now_utc - file_date) > timedelta(days=6):
        msg_blocco = "Tabelle non aggiornate. Nessun file inserito sul bucket negli ultimi 7 giorni"
        print(f"L'ultimo file '{file_name}' è del {file_date.strftime('%Y-%m-%d %H:%M:%S')}. {msg_blocco}")
        invia_notifica_telegram(msg_blocco)
        return msg_blocco, 200

    extract_to = os.path.join(MOUNT_PATH, 'extracted/')
    print(f"Cron avviato. Inizio elaborazione del file recente: '{file_name}'")

    try:
        bq_client = bigquery.Client(project=PROJECT_ID)

        if not os.path.exists(extract_to):
            os.makedirs(extract_to)

        print(f"Estrazione del file {zip_path} in corso...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print("Estrazione completata.")

        if not file_name.startswith('export_') or len(file_name) < 15:
            errore_msg = f"Formato del nome zip non valido: {file_name}"
            shutil.rmtree(extract_to, ignore_errors=True)
            print(f"Errore: {errore_msg}")
            invia_notifica_telegram(f"❌ *Errore:* {errore_msg}")
            return errore_msg, 400

        data_target = file_name[7:15]

        sqlite_files = [f for f in os.listdir(extract_to) if f.endswith('.sqlite')]
        if not sqlite_files:
            errore_msg = "Il file ZIP estratto non contiene file `.sqlite`."
            shutil.rmtree(extract_to, ignore_errors=True)
            print(f"Errore: {errore_msg}")
            invia_notifica_telegram(f"❌ *Errore:* {errore_msg}")
            return errore_msg, 400

        sqlite_path = None
        for f in sqlite_files:
            if f.startswith('export_') and f[7:15] == data_target:
                sqlite_path = os.path.join(extract_to, f)
                break
        
        if not sqlite_path:
            errore_msg = f"Nessun file `.sqlite` corrispondente alla data {data_target} trovato nello ZIP."
            shutil.rmtree(extract_to, ignore_errors=True)
            print(f"Errore: {errore_msg}")
            invia_notifica_telegram(f"❌ *Errore:* {errore_msg}")
            return errore_msg, 400

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

        processed_zip_path = f"{zip_path}.elaborato"
        os.rename(zip_path, processed_zip_path)
        print(f"File originale rinominato in: {os.path.basename(processed_zip_path)}")

        print("Processo completato con successo.")
        invia_notifica_telegram(f"✅ *Sincronizzazione Completata!*\nTutti i dati di `{file_name}` sono stati caricati su BigQuery e il file è stato archiviato.")
        
        return "Elaborazione completata con successo", 200
        
    except Exception as e:
        print(f"❌ Errore critico nel processo generale: {e}")
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)
            
        invia_notifica_telegram(f"🚨 *Errore Critico (CRON)*\nL'automazione si è interrotta sul file `{file_name}`.\n\nDettaglio errore:\n`{str(e)}`")
        return f"Errore interno: {e}", 500