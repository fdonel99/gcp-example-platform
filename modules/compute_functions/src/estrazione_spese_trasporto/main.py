import functions_framework
import os
import json
import io
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

# Inizializzazione Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)

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
# 2. LOGICA ESTRAZIONE CON GEMINI 1.5 PRO (Nativo PDF + Schema in Prompt)
# =====================================================================

def processa_pagina_pdf(pdf_bytes, numero_pagina, pydantic_schema):
    """Ritaglia la singola pagina e usa Gemini nativo per i PDF."""
    
    # Ritaglia solo la pagina specifica dal PDF per risparmiare token
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.add_page(reader.pages[numero_pagina - 1])
    
    single_page_stream = io.BytesIO()
    writer.write(single_page_stream)
    single_page_stream.seek(0)
    
    # Invia il PDF nativamente a Gemini
    pdf_part = Part.from_data(data=single_page_stream.read(), mime_type="application/pdf")
    
    # TRUCCO: Convertiamo lo schema Pydantic in formato JSON e lo mettiamo nel prompt!
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
    
    model = GenerativeModel("gemini-1.5-pro")
    
    response = model.generate_content(
        [pdf_part, prompt],
        generation_config=GenerationConfig(
            response_mime_type="application/json", # Forza l'output in JSON nativo
            # response_schema rimosso per bypassare il bug ".pop()" dell'SDK Google
            temperature=0.0 # Forza precisione chirurgica, zero creatività
        )
    )
    
    dati_json = json.loads(response.text)
    return pd.DataFrame(dati_json["righe"])

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

    # Controlli di sicurezza sulle variabili d'ambiente
    if not DESTINATION_BUCKET_NAME:
        print("ERRORE: Manca la variabile DESTINATION_BUCKET. Operazione interrotta.")
        return

    source_bucket = storage_client.bucket(source_bucket_name)
    blob = source_bucket.blob(file_name)
    
    # Download del PDF intero in RAM (veloce)
    pdf_bytes = blob.download_as_bytes()
    
    # Mappatura: (Pagina PDF, Schema Pydantic, Nome File CSV)
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
            
            # 1. Analisi dati con Vertex AI Nativo per PDF
            df = processa_pagina_pdf(pdf_bytes, pagina, schema)
            
            # 2. Conversione DataFrame in stringa CSV
            csv_data = df.to_csv(index=False)
            
            # 3. Upload nel bucket di destinazione
            out_blob = destination_bucket.blob(nome_csv)
            out_blob.upload_from_string(csv_data, content_type="text/csv")
            
            print(f"✅ File salvato con successo: gs://{DESTINATION_BUCKET_NAME}/{nome_csv}")
            
        except Exception as e:
            print(f"❌ Errore durante l'elaborazione del file {nome_csv} (Pagina {pagina}): {e}")
            error_blob = destination_bucket.blob(f"ERROR_{nome_csv}.txt")
            error_blob.upload_from_string(f"Errore estrazione: {str(e)}", content_type="text/plain")

    print(f"🎉 Elaborazione del PDF {file_name} completata su tutti e 4 i task.")