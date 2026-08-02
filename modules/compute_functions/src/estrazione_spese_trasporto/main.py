import functions_framework
import os
import json
import io
import re 
import pandas as pd
from google.cloud import storage
from pypdf import PdfReader, PdfWriter
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from pydantic import BaseModel
from typing import List, Optional

# --- Import per Google Sheets ---
import google.auth
import gspread
from gspread_dataframe import set_with_dataframe

# Inizializzazione Client Cloud Storage
storage_client = storage.Client()
DESTINATION_BUCKET_NAME = os.environ.get('DESTINATION_BUCKET')
PROJECT_ID = os.environ.get('PROJECT_ID')
VERTEX_LOCATION = 'europe-west4' 
vertexai.init(project=PROJECT_ID, location=VERTEX_LOCATION)

# ID del Google Sheet di destinazione
SPREADSHEET_ID = '1ptH6m4mS6UozgrtRUfoP_wMMwbx7wTiIn1T6eJ0Vy1c'

# Autenticazione nativa di Google Cloud per accedere a Sheets
credentials, _ = google.auth.default(scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(credentials)

# =====================================================================
# 1. DEFINIZIONE DEGLI SCHEMI PYDANTIC (Struttura esatta dei 4 CSV)
# =====================================================================

class RigaItDeA(BaseModel):
    dimensioni: str; peso: str
    UK_GBP: Optional[float]; CEP_EUR: Optional[float]; DE_EUR: Optional[float]; FR_EUR: Optional[float]; IT_EUR: Optional[float]; ES_EUR: Optional[float]; NL_EUR: Optional[float]; SE_SEK: Optional[float]; PL_PLN: Optional[float]; BE_EUR: Optional[float]
    incremento_UK_GBP: Optional[float]; incremento_CEP_EUR: Optional[float]; incremento_DE_EUR: Optional[float]; incremento_FR_EUR: Optional[float]; incremento_IT_EUR: Optional[float]; incremento_ES_EUR: Optional[float]; incremento_NL_EUR: Optional[float]; incremento_SE_SEK: Optional[float]; incremento_PL_PLN: Optional[float]; incremento_BE_EUR: Optional[float]

class TabellaItDeA(BaseModel): righe: List[RigaItDeA]

class RigaItDeB(BaseModel):
    dimensioni: str; peso: str
    UK_GBP: Optional[float]; CEP_EUR: Optional[float]; DE_EUR: Optional[float]; FR_EUR: Optional[float]; IT_EUR: Optional[float]; ES_EUR: Optional[float]; NL_EUR: Optional[float]; PL_PLN: Optional[float]; BE_EUR: Optional[float]; SE_SEK: Optional[float]
    incremento_UK_GBP: Optional[float]; incremento_CEP_EUR: Optional[float]; incremento_DE_EUR: Optional[float]; incremento_FR_EUR: Optional[float]; incremento_IT_EUR: Optional[float]; incremento_ES_EUR: Optional[float]; incremento_NL_EUR: Optional[float]; incremento_PL_PLN: Optional[float]; incremento_BE_EUR: Optional[float]; incremento_SE_SEK: Optional[float]

class TabellaItDeB(BaseModel): righe: List[RigaItDeB]

class RigaFrSpA(BaseModel):
    dimensioni: str; peso: str
    CEP_IT_ES_FR_EUR: Optional[float]; DE_EUR: Optional[float]; NL_BE_EUR: Optional[float]; SE_SEK: Optional[float]; PL_PLN: Optional[float]; UK_to_DE_FR_IT_ES_EUR: Optional[float]; UK_to_NL_EUR: Optional[float]; UK_to_SE_SEK: Optional[float]; DE_FR_IT_ES_to_UK_GBP: Optional[float]
    incremento_CEP_IT_ES_FR_EUR: Optional[float]; incremento_DE_EUR: Optional[float]; incremento_NL_BE_EUR: Optional[float]; incremento_SE_SEK: Optional[float]; incremento_PL_PLN: Optional[float]; incremento_UK_to_DE_FR_IT_ES_EUR: Optional[float]; incremento_UK_to_NL_EUR: Optional[float]; incremento_UK_to_SE_SEK: Optional[float]; incremento_DE_FR_IT_ES_to_UK_GBP: Optional[float]

class TabellaFrSpA(BaseModel): righe: List[RigaFrSpA]

class RigaFrSpB(BaseModel):
    dimensioni: str; peso: str
    CEP_EUR: Optional[float]; DE_EUR: Optional[float]; FR_EUR: Optional[float]; IT_EUR: Optional[float]; ES_EUR: Optional[float]; NL_BE_EUR: Optional[float]; PL_PLN: Optional[float]; SE_SEK: Optional[float]; DE_FR_IT_ES_to_UK_GBP: Optional[float]; UK_to_DE_FR_IT_ES_EUR: Optional[float]; UK_to_NL_BE_EUR: Optional[float]; UK_to_SE_SEK: Optional[float]; UK_to_DE_FR_IT_ES_GBP: Optional[float]
    incremento_CEP_EUR: Optional[float]; incremento_DE_EUR: Optional[float]; incremento_FR_EUR: Optional[float]; incremento_IT_EUR: Optional[float]; incremento_ES_EUR: Optional[float]; incremento_NL_BE_EUR: Optional[float]; incremento_PL_PLN: Optional[float]; incremento_SE_SEK: Optional[float]; incremento_DE_FR_IT_ES_to_UK_GBP: Optional[float]; incremento_UK_to_DE_FR_IT_ES_EUR: Optional[float]; incremento_UK_to_NL_BE_EUR: Optional[float]; incremento_UK_to_SE_SEK: Optional[float]; incremento_UK_to_DE_FR_IT_ES_GBP: Optional[float]

class TabellaFrSpB(BaseModel): righe: List[RigaFrSpB]

# =====================================================================
# 2. LOGICA ESTRAZIONE CON GEMINI 2.5 PRO E PULIZIA PANDAS
# =====================================================================

def processa_pagina_pdf(pdf_bytes, numero_pagina, pydantic_schema):
    """Ritaglia la singola pagina e usa Gemini nativo per i PDF."""
    
    # Ritaglia solo la pagina specifica dal PDF
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.add_page(reader.pages[numero_pagina - 1])
    
    single_page_stream = io.BytesIO()
    writer.write(single_page_stream)
    single_page_stream.seek(0)
    
    # Invia il PDF nativamente a Gemini
    pdf_part = Part.from_data(data=single_page_stream.read(), mime_type="application/pdf")
    
    schema_json = json.dumps(pydantic_schema.model_json_schema(), indent=2)
    
    prompt = f"""
    Sei un estrattore dati specializzato in logistica. Leggi la tabella tariffaria presente in questo documento PDF.
    Estrai i dati e popolali esattamente secondo questo schema JSON:
    
    {schema_json}
    
    REGOLE RIGOROSE:
    1. Se vedi un incremento tariffario (es. '+0,18/kg' o '+0,05 per/+100g'), mettilo nei campi 'incremento_', inserendo SOLO il numero '0.18'.
    2. Rimuovi lettere, simboli '+', '/', 'kg', 'g', e valute.
    3. Converti le virgole in punti decimali ('2,50' -> 2.50).
    4. Cerca di associare le fasce incrementali alle fasce di peso base corrispondenti per restituire un record omogeneo.
    5. Se un dato non è applicabile o manca, restituisci null.
    """
    
    model = GenerativeModel("gemini-2.5-pro")
    
    response = model.generate_content(
        [pdf_part, prompt],
        generation_config=GenerationConfig(
            response_mime_type="application/json", 
            temperature=0.0 
        )
    )
    
    dati_json = json.loads(response.text)
    df = pd.DataFrame(dati_json["righe"])

    # --- INIZIO POST-PROCESSING PANDAS ---
    def pulisci_dimensioni(val):
        if pd.isna(val) or val is None:
            return val
        return str(val).split(':')[0].strip()

    def pulisci_peso(val):
        if pd.isna(val) or val is None:
            return val
        
        testo = str(val).lower()
        is_kg = 'kg' in testo
        testo = testo.replace(',', '.')
        
        match = re.search(r'(\d+\.?\d*)', testo)
        if match:
            numero = float(match.group(1))
            if is_kg:
                numero = numero * 1000
            
            # Nota: restituiamo il numero come INT (non str) così Google Sheets 
            # e i file CSV lo capiscono in automatico come valore numerico
            return int(numero)
        
        return val
    
    if 'dimensioni' in df.columns:
        df['dimensioni'] = df['dimensioni'].apply(pulisci_dimensioni)
        
    if 'peso' in df.columns:
        df['peso'] = df['peso'].apply(pulisci_peso)

    return df

# =====================================================================
# 3. ENTRY POINT DELLA CLOUD FUNCTION
# =====================================================================

@functions_framework.cloud_event
def estrai_tariffe_pdf(cloud_event):
    """
    Attivata automaticamente quando un nuovo PDF viene caricato sul bucket.
    Estrae i dati tramite Vertex AI, salva i CSV e aggiorna il Google Sheet.
    """
    data = cloud_event.data
    source_bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Iniziata elaborazione di {file_name} caricato in gs://{source_bucket_name}")
    
    if not file_name.lower().endswith(".pdf"):
        print("Il file non è un PDF. Operazione ignorata.")
        return

    if not DESTINATION_BUCKET_NAME:
        print("ERRORE: Manca la variabile DESTINATION_BUCKET. Impossibile salvare i CSV.")
        return

    # Download del PDF
    source_bucket = storage_client.bucket(source_bucket_name)
    blob = source_bucket.blob(file_name)
    pdf_bytes = blob.download_as_bytes()
    
    # Mappatura: (Pagina, Schema, Nome CSV Base, Nome Foglio Google Sheet)
    tasks = [
        (6, TabellaItDeA, "df_costi_it_de_A", "IT_DE_A"),
        (7, TabellaItDeB, "df_costi_it_de_B", "IT_DE_B"),
        (10, TabellaFrSpA, "df_costi_fr_sp_A", "FR_SP_A"),
        (11, TabellaFrSpB, "df_costi_fr_sp_B", "FR_SP_B")
    ]
    
    destination_bucket = storage_client.bucket(DESTINATION_BUCKET_NAME)

    # Connessione a Google Sheets
    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print(f"Errore di accesso al Google Sheet (ID: {SPREADSHEET_ID}): {e}. Controlla i permessi del Service Account.")
        return

    for pagina, schema, nome_csv_base, nome_tab_sheet in tasks:
        nome_csv = f"{nome_csv_base}.csv"
        
        try:
            print(f"Estrazione pagina {pagina} per {nome_csv_base} / tab {nome_tab_sheet}...")
            
            df = processa_pagina_pdf(pdf_bytes, pagina, schema)
            
            # --- AZIONE 1: SCRITTURA SU BUCKET (CSV) ---
            csv_data = df.to_csv(index=False)
            out_blob = destination_bucket.blob(nome_csv)
            out_blob.upload_from_string(csv_data, content_type="text/csv")
            print(f"✅ CSV salvato: gs://{DESTINATION_BUCKET_NAME}/{nome_csv}")

            # --- AZIONE 2: SCRITTURA SU GOOGLE SHEETS ---
            try:
                worksheet = spreadsheet.worksheet(nome_tab_sheet)
            except gspread.exceptions.WorksheetNotFound:
                print(f"Il foglio '{nome_tab_sheet}' non esiste. Lo creo...")
                worksheet = spreadsheet.add_worksheet(title=nome_tab_sheet, rows="100", cols="30")
            
            # Svuota i vecchi dati presenti nel foglio
            worksheet.clear()
            
            # Inserisce la nuova tabella
            set_with_dataframe(worksheet, df, resize=True)
            print(f"✅ Dati salvati in Google Sheets (Foglio: {nome_tab_sheet})")
            
        except Exception as e:
            print(f"❌ Errore durante l'elaborazione del task {nome_csv_base} (Pagina {pagina}): {e}")
            error_blob = destination_bucket.blob(f"ERROR_{nome_csv_base}.txt")
            error_blob.upload_from_string(f"Errore estrazione: {str(e)}", content_type="text/plain")

    print(f"🎉 Elaborazione completata per tutti i listini!")