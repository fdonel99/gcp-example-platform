import functions_framework
import os
import json
import fitz  # PyMuPDF
import pandas as pd
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from pydantic import BaseModel, Field
from typing import List, Optional

# Inizializzazione Client Cloud Storage
storage_client = storage.Client()
DESTINATION_BUCKET_NAME = os.environ.get('DESTINATION_BUCKET')
PROJECT_ID = os.environ.get('PROJECT_ID')
LOCATION = os.environ.get('LOCATION', 'europe-west4')

# Inizializzazione Vertex AI usando l'identità della Cloud Function
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
# 2. LOGICA ESTRAZIONE OCR
# =====================================================================

def processa_pagina_ocr(pdf_doc, numero_pagina, pydantic_schema):
    """Renderizza la pagina in immagine e sfrutta Gemini per l'estrazione strutturata."""
    page = pdf_doc.load_page(numero_pagina - 1)
    pix = page.get_pixmap(dpi=200)
    image_bytes = pix.tobytes("png")
    
    image_part = Part.from_data(data=image_bytes, mime_type="image/png")
    
    prompt = """
    Sei un estrattore dati specializzato in logistica. Leggi la tabella tariffaria nell'immagine.
    Estrai i dati e popolali esattamente secondo lo schema fornito.
    REGOLE RIGOROSE:
    1. Se vedi un incremento tariffario (es. '+0,18/kg' o '+0,05 per/+100g'), mettilo nei campi 'incremento_', inserendo SOLO il numero '0.18'.
    2. Rimuovi lettere, simboli '+', '/', 'kg', 'g', e valute.
    3. Converti le virgole in punti decimali ('2,50' -> 2.50).
    4. Cerca di associare le fasce incrementali alle fasce di peso base corrispondenti per restituire un record omogeneo.
    5. Se un dato non è applicabile o manca, restituisci null.
    """
    
    # Utilizziamo Gemini 1.5 Pro per la migliore accuratezza visiva e logica
    model = GenerativeModel("gemini-1.5-pro")
    
    response = model.generate_content(
        [image_part, prompt],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=pydantic_schema,
            temperature=0.0 # Impedisce risposte creative/allucinate
        )
    )
    
    dati_json = json.loads(response.text)
    return pd.DataFrame(dati_json["righe"])

# =====================================================================
# 3. ENTRY POINT DELLA CLOUD FUNCTION
# =====================================================================

@functions_framework.cloud_event
def elabora_spese_trasporto(cloud_event):
    data = cloud_event.data
    source_bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Iniziata elaborazione di {file_name} caricato in gs://{source_bucket_name}")
    
    if not file_name.lower().endswith(".pdf"):
        print("Il file non è un PDF. Operazione ignorata.")
        return

    source_bucket = storage_client.bucket(source_bucket_name)
    blob = source_bucket.blob(file_name)
    
    # Download del file in RAM
    pdf_bytes = blob.download_as_bytes()
    pdf_doc = fitz.open("pdf", pdf_bytes)
    
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
            
            # 1. Analisi visiva della tabella
            df = processa_pagina_ocr(pdf_doc, pagina, schema)
            
            # 2. Conversione DataFrame in stringa CSV
            csv_data = df.to_csv(index=False)
            
            # 3. Upload nel bucket di destinazione
            out_blob = destination_bucket.blob(nome_csv)
            out_blob.upload_from_string(csv_data, content_type="text/csv")
            
            print(f"File salvato con successo: gs://{DESTINATION_BUCKET_NAME}/{nome_csv}")
            
        except Exception as e:
            print(f"Errore durante l'elaborazione del file {nome_csv} (Pagina {pagina}): {e}")
            
            # Creazione di un file di log nel bucket per monitorare gli errori
            error_blob = destination_bucket.blob(f"ERROR_{nome_csv}.txt")
            error_blob.upload_from_string(f"Errore estrazione: {str(e)}", content_type="text/plain")

    pdf_doc.close()
    print(f"Elaborazione del PDF {file_name} completata su tutti e 4 i task.")