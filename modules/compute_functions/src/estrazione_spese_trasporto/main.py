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

# Inizializzazione Client Cloud Storage
storage_client = storage.Client()
DESTINATION_BUCKET_NAME = os.environ.get('DESTINATION_BUCKET')
PROJECT_ID = os.environ.get('PROJECT_ID')
LOCATION = os.environ.get('LOCATION', 'europe-west4')
VERTEX_LOCATION = 'europe-west4' 
vertexai.init(project=PROJECT_ID, location=VERTEX_LOCATION)

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
    1. ATTENZIONE AL TESTO NASCOSTO (CRITICO): Il livello di testo di questo PDF è corrotto. Sotto i numeri visibili sono rimaste incastrate vecchie tariffe invisibili (es. 2.50, 2.51 nella colonna SE_SEK). DEVI IGNORARE il testo nascosto. Usa ESCLUSIVAMENTE la tua visione ottica per leggere i numeri stampati visibilmente sulla pagina (es. 60.01, 60.11, 64.08).
    2. Non unire mai due o più numeri nello stesso campo. Ogni colonna ha il suo valore separato.
    3. Se vedi un incremento tariffario (es. '+0,18/kg' o '+0,05 per/+100g'), mettilo nei campi 'incremento_', inserendo SOLO il numero '0.18'.
    4. Rimuovi lettere, simboli '+', '/', 'kg', 'g', e valute.
    5. Converti le virgole in punti decimali ('2,50' -> 2.50).
    6. Se un dato non è applicabile o manca, restituisci null.
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

    # --- INIZIO POST-PROCESSING DETERMINISTICO IN PYTHON ---
    
    def pulisci_dimensioni(val):
        if pd.isna(val) or val is None:
            return val
        # Divide alla prima occorrenza di ":" e prende il primo pezzo rimuovendo gli spazi extra
        return str(val).split(':')[0].strip()

    def pulisci_peso(val):
        if pd.isna(val) or val is None:
            return val
        
        testo = str(val).lower()
        is_kg = 'kg' in testo
        
        # Sostituisce eventuali virgole con il punto decimale
        testo = testo.replace(',', '.')
        
        # Estrae i numeri, inclusi eventuali decimali (es. da "≤ 3.90 kg" estrae "3.90")
        match = re.search(r'(\d+\.?\d*)', testo)
        if match:
            numero = float(match.group(1))
            
            # Se la stringa originale conteneva "kg", moltiplica per 1000
            if is_kg:
                numero = numero * 1000
                
            # Restituisce il numero come stringa intera (es: 3900 invece di 3900.0)
            return str(int(numero))
        
        return str(val) # Fallback in caso di valore inaspettato senza numeri
    
    # Applica le funzioni di pulizia alle colonne
    if 'dimensioni' in df.columns:
        df['dimensioni'] = df['dimensioni'].apply(pulisci_dimensioni)
        
    if 'peso' in df.columns:
        df['peso'] = df['peso'].apply(pulisci_peso)
        
    # --- FINE POST-PROCESSING ---

    return df

# =====================================================================
# 3. ENTRY POINT DELLA CLOUD FUNCTION
# =====================================================================

@functions_framework.cloud_event
def estrai_tariffe_pdf(cloud_event):
    """
    Attivata automaticamente quando un nuovo PDF viene caricato sul bucket.
    Estrae i dati tramite Vertex AI e salva 4 file CSV.
    """
    data = cloud_event.data
    source_bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Iniziata elaborazione di {file_name} caricato in gs://{source_bucket_name}")
    
    if not file_name.lower().endswith(".pdf"):
        print("Il file non è un PDF. Operazione ignorata.")
        return

    if not DESTINATION_BUCKET_NAME:
        print("ERRORE: Manca la variabile DESTINATION_BUCKET. Operazione interrotta.")
        return

    source_bucket = storage_client.bucket(source_bucket_name)
    blob = source_bucket.blob(file_name)
    
    pdf_bytes = blob.download_as_bytes()
    
    tasks = [
        (6, TabellaItDeA, "df_costi_it_de_A.csv"),
        (7, TabellaItDeB, "df_costi_it_de_B.csv"),
        (10, TabellaFrSpA, "df_costi_fr_sp_A.csv"),
        (11, TabellaFrSpB, "df_costi_fr_sp_B.csv")
    ]
    
    destination_bucket = storage_client.bucket(DESTINATION_BUCKET_NAME)

    for pagina, schema, nome_csv in tasks:
        try:
            print(f"Estrazione pagina {pagina} per la creazione di {nome_csv}...")
            
            df = processa_pagina_pdf(pdf_bytes, pagina, schema)
            
            csv_data = df.to_csv(index=False)
            
            out_blob = destination_bucket.blob(nome_csv)
            out_blob.upload_from_string(csv_data, content_type="text/csv")
            
            print(f"✅ File salvato con successo: gs://{DESTINATION_BUCKET_NAME}/{nome_csv}")
            
        except Exception as e:
            print(f"❌ Errore durante l'elaborazione del file {nome_csv} (Pagina {pagina}): {e}")
            error_blob = destination_bucket.blob(f"ERROR_{nome_csv}.txt")
            error_blob.upload_from_string(f"Errore estrazione: {str(e)}", content_type="text/plain")

    print(f"🎉 Elaborazione del PDF {file_name} completata su tutti e 4 i task.")