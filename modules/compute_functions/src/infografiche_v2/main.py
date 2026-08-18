import os
import json
from google.cloud import documentai

# ==========================================
# CONFIGURAZIONE (Inserisci i tuoi dati)
# ==========================================
PROJECT_ID = os.environ.get("PROJECT_ID", "IL_TUO_PROJECT_ID")
LOCATION = "eu"  # Come abbiamo impostato su Terraform
PROCESSOR_ID = os.environ.get("PROCESSOR_ID", "IL_TUO_PROCESSOR_ID")

# Se testi in locale, assicurati che questa variabile d'ambiente punti al tuo JSON delle chiavi
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/percorso/al/tuo/file/chiavi.json"

def estrai_testo_da_segmento(text_anchor, testo_completo):
    """Estrae la sottostringa di testo usando gli indici forniti da Document AI"""
    testo = ""
    for segment in text_anchor.text_segments:
        start_index = int(segment.start_index)
        end_index = int(segment.end_index)
        testo += testo_completo[start_index:end_index]
    return testo.strip()

def analizza_immagine_con_document_ai(file_path):
    print(f"🔄 Inizio analisi dell'immagine: {file_path}")
    
    # Inizializza il client
    client = documentai.DocumentProcessorServiceClient()
    name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    # Leggi l'immagine dal disco locale
    with open(file_path, "rb") as image:
        image_content = image.read()

    # Prepara la richiesta per Document AI
    raw_document = documentai.RawDocument(
        content=image_content, 
        mime_type="image/jpeg"
    )
    request = documentai.ProcessRequest(
        name=name, 
        raw_document=raw_document
    )

    print("📡 Chiamata a Google Cloud Document AI in corso...")
    result = client.process_document(request=request)
    document = result.document
    testo_completo = document.text

    print("✅ Risposta ricevuta. Estrazione gerarchia e stile...")
    
    risultato_strutturato = []

    # Esploriamo la struttura: Pagine -> Blocchi -> Paragrafi -> Token (Parole)
    for pagina in document.pages:
        img_width = pagina.dimension.width
        img_height = pagina.dimension.height
        
        for id_blocco, blocco in enumerate(pagina.blocks):
            blocco_dati = {
                "id_blocco": id_blocco,
                "parole": []
            }
            
            for paragrafo in blocco.paragraphs:
                for token in paragrafo.tokens:
                    # 1. Estrai il testo esatto
                    testo_parola = estrai_testo_da_segmento(token.layout.text_anchor, testo_completo)
                    if not testo_parola:
                        continue

                    # 2. Estrai lo Stile (Grassetto)
                    is_bold = False
                    if token.style_info:
                        is_bold = token.style_info.bold
                        
                    # 3. Estrai le Coordinate (Convertiamo i vertici normalizzati [0-1] in pixel assoluti)
                    vertici = []
                    if token.layout.bounding_poly.normalized_vertices:
                        for v in token.layout.bounding_poly.normalized_vertices:
                            vertici.append({
                                "x": int(v.x * img_width),
                                "y": int(v.y * img_height)
                            })
                            
                    blocco_dati["parole"].append({
                        "testo": testo_parola,
                        "bold": is_bold,
                        "vertici": vertici
                    })
            
            # Aggiungiamo il blocco solo se contiene effettivamente delle parole
            if blocco_dati["parole"]:
                risultato_strutturato.append(blocco_dati)

    return risultato_strutturato

if __name__ == "__main__":
    nome_file = "esempio_infografica.jpg"
    
    try:
        dati_estratti = analizza_immagine_con_document_ai(nome_file)
        
        # Salviamo il risultato in un file JSON per ispezionarlo comodamente
        output_json = "output_step1.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(dati_estratti, f, ensure_ascii=False, indent=2)
            
        print(f"\n🎉 Estrazione completata! I dati strutturati sono stati salvati in '{output_json}'")
        
    except Exception as e:
        print(f"\n❌ Errore durante l'esecuzione: {e}")