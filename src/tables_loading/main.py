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
from datetime import datetime, timedelta, timezone  # <-- NUOVI IMPORT AGGIUNTI
import functions_framework

# Import Cloud e Dati
from google.cloud import bigquery
import polars as pl

# --- CONFIGURAZIONE TELEGRAM ---
TELEGRAM_TOKEN = '8906093462:AAFi_3hQum83NXR7dMYLu0RZXKDLvJwdGro'
TELEGRAM_CHAT_ID = '5122727806'

# --- CONFIGURAZIONE CLOUD ---
PROJECT_ID = 'cloud-platform-northstar'
DATASET_ID = 'NORTHSTAR'
BUCKET_NAME = 'bkt-export-ns-zip' # Nome del bucket ricavato dai tuoi log
MOUNT_PATH = '/mnt/bucket'    # Percorso GCS Fuse

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
    # Cerca solo i file che finiscono esattamente con .zip (ignora i .zip.elaborato)
    list_of_files = glob.glob(os.path.join(MOUNT_PATH, '*.zip'))
    
    # ---> CONTROLLO: SE NON CI SONO FILE <---
    if not list_of_files:
        msg_blocco = "Tabelle non aggiornate. Nessun file inserito sul bucket negli ultimi 7 giorni"
        print(msg_blocco)
        invia_notifica_telegram(msg_blocco)
        return msg_blocco, 200

    # Prendi il file più recente in base alla data di creazione nel bucket
    zip_path = max(list_of_files, key=os.path.getctime)
    file_name = os.path.basename(zip_path)
    
    # ---> INIZIO CONTROLLO DEI 6 GIORNI SUL FILE <---
    # Ricaviamo il timestamp di creazione/modifica del file dal filesystem
    file_timestamp = os.path.getctime(zip_path)
    file_date = datetime.fromtimestamp(file_timestamp, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    
    # Se il file più recente è più vecchio di 6 giorni, blocca l'esecuzione
    if (now_utc - file_date) > timedelta(days=6):
        msg_blocco = "Tabelle non aggiornate. Nessun file inserito sul bucket negli ultimi 6 giorni"
        print(f"L'ultimo file '{file_name}' è del {file_date.strftime('%Y-%m-%d %H:%M:%S')}. {msg_blocco}")
        invia_notifica_telegram(msg_blocco)
        return msg_blocco, 200
    # ---> FINE CONTROLLO DEI 6 GIORNI <---

    extract_to = os.path.join(MOUNT_PATH, 'extracted/')
    print(f"Cron avviato. Inizio elaborazione del file recente: '{file_name}'")

    try:
        bq_client = bigquery.Client(project=PROJECT_ID)

        # 2. ESTRAZIONE SQLITE IN RAM E SELEZIONE FILE CORRETTO
        if not os.path.exists(extract_to):
            os.makedirs(extract_to)

        print(f"Estrazione del file {zip_path} in /tmp in corso...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print("Estrazione completata.")

        # Controllo di sicurezza sul nome del file ZIP
        if not file_name.startswith('export_') or len(file_name) < 15:
            errore_msg = f"Formato del nome zip non valido: {file_name}"
            shutil.rmtree(extract_to, ignore_errors=True)
            print(f"Errore: {errore_msg}")
            invia_notifica_telegram(f"❌ *Errore:* {errore_msg}")
            return errore_msg, 400

        # Estrai la data (8 caratteri) dal nome del file ZIP principale (es: export_20260718_*.zip)
        data_target = file_name[7:15]

        sqlite_files = [f for f in os.listdir(extract_to) if f.endswith('.sqlite')]
        if not sqlite_files:
            errore_msg = "Il file ZIP estratto non contiene file `.sqlite`."
            shutil.rmtree(extract_to, ignore_errors=True)
            print(f"Errore: {errore_msg}")
            invia_notifica_telegram(f"❌ *Errore:* {errore_msg}")
            return errore_msg, 400

        # Cerca il file specifico in base alla data
        sqlite_path = None
        for f in sqlite_files:
            if f.startswith('export_') and f[7:15] == data_target:
                sqlite_path = os.path.join(extract_to, f)
                break
        
        # Se non viene trovato il DB corrispondente, blocca tutto e pulisci la memoria
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

        # 3. ELABORAZIONE ASINCRONA DELLE TABELLE
        bq_jobs = []
        parquets_da_eliminare = []

        for t_name in tables:
            try:
                clean_table_name = t_name.replace(' ', '_').replace('-', '_')
                table_id = f"{PROJECT_ID}.{DATASET_ID}.{clean_table_name}"
                
                # Salviamo il parquet nel bucket GCS Fuse (0 impatto sulla RAM)
                parquet_filename = f"{clean_table_name}_temp.parquet"
                parquet_path = os.path.join(MOUNT_PATH, parquet_filename)
                
                # URI nativo GCS per far leggere il file a BigQuery ad altissima velocità
                gcs_uri = f"gs://{BUCKET_NAME}/{parquet_filename}"
                
                print(f"Lettura tabella {t_name} ed esportazione in Parquet su GCS...")
                query = f"SELECT * FROM {t_name}"
                
                df = pl.read_database_uri(query=query, uri=sqlite_uri)
                df.write_parquet(parquet_path)
                
                # Svuotamento immediato della RAM
                del df 
                gc.collect()
                
                print(f"Avvio job asincrono su BigQuery per {t_name}...")
                job_config = bigquery.LoadJobConfig(
                    source_format=bigquery.SourceFormat.PARQUET,
                    write_disposition="WRITE_TRUNCATE",
                )
                
                # Affidiamo il caricamento a BigQuery senza aspettare che finisca subito
                job = bq_client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
                
                bq_jobs.append((t_name, job))
                parquets_da_eliminare.append(parquet_path)
                    
            except Exception as table_error:
                print(f"❌ Errore durante l'elaborazione della tabella {t_name}: {table_error}")
                if 'df' in locals():
                    del df
                    gc.collect()

        # 4. ATTESA COMPLETAMENTO JOB BIGQUERY
        print("Tutti i dati estratti. Attesa che BigQuery completi i caricamenti in parallelo...")
        for t_name, job in bq_jobs:
            try:
                job.result() # Ora Python aspetta la conferma da BQ
                print(f"✅ Tabella confermata: {t_name}")
            except Exception as e:
                print(f"❌ Errore segnalato da BigQuery per {t_name}: {e}")

        # 5. PULIZIA E RINOMINA FILE
        print("Rimozione dei file Parquet temporanei dal bucket...")
        for p_path in parquets_da_eliminare:
            if os.path.exists(p_path):
                os.remove(p_path)

        # Pulizia robusta: cancella tutta la cartella estratta (tutti i db, zip interni e log)
        print("Svuotamento RAM: rimozione dell'intera cartella estratta...")
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)

        # Rinomina il file ZIP per non rielaborarlo al prossimo avvio del Cron
        processed_zip_path = f"{zip_path}.elaborato"
        os.rename(zip_path, processed_zip_path)
        print(f"File originale rinominato in: {os.path.basename(processed_zip_path)}")

        print("Processo completato con successo.")
        invia_notifica_telegram(f"✅ *Sincronizzazione Completata!*\nTutti i dati di `{file_name}` sono stati caricati su BigQuery e il file è stato archiviato.")
        
        return "Elaborazione completata con successo", 200
        
    except Exception as e:
        print(f"❌ Errore critico nel processo generale: {e}")
        # In caso di errore inaspettato, proviamo comunque a liberare la RAM
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)
            
        invia_notifica_telegram(f"🚨 *Errore Critico (CRON)*\nL'automazione si è interrotta sul file `{file_name}`.\n\nDettaglio errore:\n`{str(e)}`")
        return f"Errore interno: {e}", 500