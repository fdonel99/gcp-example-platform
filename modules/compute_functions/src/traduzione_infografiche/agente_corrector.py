import json
import time
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.api_core.exceptions import ResourceExhausted

PROJECT_ID = "cloud-platform-northstar-test"
LOCATION_VERTEX = "global" 
vertexai.init(project=PROJECT_ID, location=LOCATION_VERTEX)

def agente_corrector(original_image_path, translated_image_path, target_lang, motivo_ko, traduzioni_attive, json_estratti):
    print(f"\n🛠️ Innesco Agente Corrector (Risoluzione Universale) per: {target_lang}...")
    
    with open(original_image_path, "rb") as f:
        img_orig = Part.from_data(data=f.read(), mime_type="image/jpeg")
        
    with open(translated_image_path, "rb") as f:
        img_trad = Part.from_data(data=f.read(), mime_type="image/jpeg")

    testi_in_uso = {}
    for trad in traduzioni_attive:
        testo = trad.get("testi_tradotti", {}).get(target_lang, "")
        testi_in_uso[trad["id_blocco"]] = testo

    testi_ocr = {b["id_blocco"]: [p["testo"] for p in b["parole"]] for b in json_estratti}

    prompt = [
        f"Sei il Direttore di Impaginazione per infografiche. Lingua target: {target_lang}.",
        "Immagine 1 (Originale corretta):", img_orig,
        "Immagine 2 (Traduzione SCARTATA):", img_trad,
        f"Il QA ha SCARTATO l'Immagine 2 per questo motivo: '{motivo_ko}'",
        f"Testi attualmente stampati con i loro ID logici: {json.dumps(testi_in_uso, ensure_ascii=False)}",
        f"Dati OCR originali dell'immagine (id_blocco -> array di parole): {json.dumps(testi_ocr, ensure_ascii=False)}",
        
        "COMPITO: Risolvi i problemi di layout applicando queste strategie:",
        "1. TESTO PIÙ COMPATTO: Se il testo entra in collisione, inserisci ritorni a capo ('\\n') o abbrevialo.",
        "2. SCUDO E AUTO-ALLINEAMENTO: Se il problema è vicino a un logo (es. 'NO Chemicals'), proteggi le sue parole in 'parole_da_preservare'.",
        "3. OFFSET GEOMETRICO: Se usi lo scudo, lascia gli offset a 0.0. Usali solo se strettamente necessario.",
        "4. FORMATTAZIONE MARKDOWN: Preserva SEMPRE il grassetto originale utilizzando gli asterischi doppi (**).",
        
        "5. GESTIONE DEGLI ID (CRITICO): Devi distinguere tra testi già stampati e testi mancanti.",
        "- Se correggi un testo già presente in Immagine 2, usa 'id_blocco_logico' corrispondente al suo ID nei 'Testi attualmente stampati' e imposta 'id_ocr_mancante' a null.",
        "- Se il QA segnala un testo MANCANTE (non tradotto/rimasto in italiano), cercalo nei 'Dati OCR originali', usa il suo ID in 'id_ocr_mancante' e imposta 'id_blocco_logico' a null.",
        
        "Restituisci SOLO un JSON valido strutturato così:",
        "{\n  \"ragionamento\": \"...\",\n  \"correzioni\": [\n    {\n      \"id_blocco_logico\": 2,\n      \"id_ocr_mancante\": null,\n      \"nuovo_testo\": \"**TESTO**\\n**TRADOTTO**\",\n      \"offset_x_pct\": 0.0,\n      \"offset_y_pct\": 0.0,\n      \"parole_da_preservare\": [\"Logo\"]\n    }\n  ]\n}"
    ]

    model = GenerativeModel("gemini-3.6-flash") 
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            risultato = json.loads(response.text)
            print(f"💡 Strategia IA: {risultato.get('ragionamento')}")
            return risultato
        except ResourceExhausted:
            if attempt < max_retries - 1:
                time.sleep(60)
            else:
                return {}
        except Exception as e:
            print(f"❌ Errore Corrector: {e}")
            return {}