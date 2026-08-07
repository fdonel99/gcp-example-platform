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
import google.auth
import gspread
from gspread_dataframe import set_with_dataframe, get_as_dataframe

storage_client = storage.Client()
PROJECT_ID = os.environ.get('PROJECT_ID')
VERTEX_LOCATION = 'europe-west4' 
vertexai.init(project=PROJECT_ID, location=VERTEX_LOCATION)
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1TYpxmD6H_9v-ZeeOqSZqiHF50cyzj6xpg51zTaTEQWE')

credentials, _ = google.auth.default(scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(credentials)

# =====================================================================
# 1. DEFINIZIONE DEGLI SCHEMI PYDANTIC (Struttura esatta dei 4 fogli)
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
    
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.add_page(reader.pages[numero_pagina - 1])
    
    single_page_stream = io.BytesIO()
    writer.write(single_page_stream)
    single_page_stream.seek(0)
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
    6. CORREZIONE ERRORI DEL PDF (MOLTO IMPORTANTE): 
       - Amazon ha commesso un errore di battitura: la riga con dimensioni (40 x 30 x 6 cm) è chiamata erroneamente "Pacco piccolo 1". Tu DEVI rinominarla in "Pacco medio 1".
       - Il simbolo '≤' attaccato ai numeri a volte viene letto male (es. '1≤' letto come '1s' o '1a'). Ignora queste lettere finali fantasma e restituisci solo il nome corretto della classe (es. "Pacco piccolo 3", "Pacco grande 2").
    """
    
    model = GenerativeModel(
        "gemini-2.5-pro",
        labels={"scopo": "estrazione-tariffe-pdf"}
        )
    
    response = model.generate_content(
        [pdf_part, prompt],
        generation_config=GenerationConfig(
            response_mime_type="application/json", 
            temperature=0.0 
        )
    )
    
    dati_json = json.loads(response.text)
    df = pd.DataFrame(dati_json["righe"])

    def pulisci_dimensioni(val):
        if pd.isna(val) or val is None:
            return val
        
        testo_pulito = re.split(r'[:≤<]', str(val))[0]
        return testo_pulito.strip()

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
    Estrae i dati tramite Vertex AI e aggiorna il Google Sheet.
    """
    data = cloud_event.data
    source_bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Iniziata elaborazione di {file_name} caricato in gs://{source_bucket_name}")
    
    if not file_name.lower().endswith(".pdf"):
        print("Il file non è un PDF. Operazione ignorata.")
        return

    source_bucket = storage_client.bucket(source_bucket_name)
    
    try:
        tutti_i_file = source_bucket.list_blobs()
        for file_esistente in tutti_i_file:
            if file_esistente.name != file_name:
                print(f"🧹 Pulizia: Elimino il vecchio listino '{file_esistente.name}'")
                file_esistente.delete()
    except Exception as e:
        print(f"⚠️ Attenzione: Impossibile eliminare i vecchi file. Errore: {e}")

    blob = source_bucket.blob(file_name)
    pdf_bytes = blob.download_as_bytes()

    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print(f"Errore di accesso al Google Sheet (ID: {SPREADSHEET_ID}): {e}. Controlla i permessi del Service Account.")
        return

    try:
        worksheet_indice = spreadsheet.worksheet("INDICE")
        df_indice = get_as_dataframe(worksheet_indice).dropna(how='all', axis=0).dropna(how='all', axis=1)
        df_indice.columns = df_indice.columns.astype(str).str.lower().str.strip()

        def ottieni_pagina(regione, classe):
            risultato = df_indice[
                (df_indice['regione'].astype(str).str.upper() == regione.upper()) &
                (df_indice['classe'].astype(str).str.upper() == classe.upper())
            ]
            if not risultato.empty:
                return int(risultato['pagina'].iloc[0])
            raise ValueError(f"Impossibile trovare la pagina per Regione: {regione}, Classe: {classe} nel foglio INDICE.")

        pagina_it_de_a = ottieni_pagina("IT_DE", "A")
        pagina_it_de_b = ottieni_pagina("IT_DE", "B")
        pagina_fr_sp_a = ottieni_pagina("FR_SP", "A")
        pagina_fr_sp_b = ottieni_pagina("FR_SP", "B")
        
        print(f"Pagine dinamiche estratte: IT_DE_A={pagina_it_de_a}, IT_DE_B={pagina_it_de_b}, FR_SP_A={pagina_fr_sp_a}, FR_SP_B={pagina_fr_sp_b}")
        
    except Exception as e:
        print(f"❌ Errore durante la lettura del foglio 'INDICE': {e}")
        return

    tasks = [
        (pagina_it_de_a, TabellaItDeA, "IT_DE_A"),
        (pagina_it_de_b, TabellaItDeB, "IT_DE_B"),
        (pagina_fr_sp_a, TabellaFrSpA, "FR_SP_A"),
        (pagina_fr_sp_b, TabellaFrSpB, "FR_SP_B")
    ]
    
    for pagina, schema, nome_tab_sheet in tasks:
        try:
            print(f"Estrazione pagina {pagina} per il tab {nome_tab_sheet}...")
            
            df = processa_pagina_pdf(pdf_bytes, pagina, schema)

            try:
                worksheet = spreadsheet.worksheet(nome_tab_sheet)
            except gspread.exceptions.WorksheetNotFound:
                print(f"Il foglio '{nome_tab_sheet}' non esiste. Lo creo...")
                worksheet = spreadsheet.add_worksheet(title=nome_tab_sheet, rows="100", cols="30")
            
            worksheet.clear()
            set_with_dataframe(worksheet, df, resize=True)
            print(f"✅ Dati salvati in Google Sheets (Foglio: {nome_tab_sheet})")
            
        except Exception as e:
            print(f"❌ Errore durante l'elaborazione del tab {nome_tab_sheet} (Pagina {pagina}): {e}")

    print(f"🎉 Elaborazione completata per tutti i listini!")