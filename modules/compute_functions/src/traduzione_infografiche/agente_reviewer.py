import json
import time
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.api_core.exceptions import ResourceExhausted

PROJECT_ID = "cloud-platform-northstar-test"
LOCATION_VERTEX = "global" 
vertexai.init(project=PROJECT_ID, location=LOCATION_VERTEX)

def agente_reviewer(original_image_path, translated_image_path, target_lang):
    print(f"\n🧐 Innesco Agente QA per la lingua: {target_lang}...")
    
    with open(original_image_path, "rb") as f:
        img_orig = Part.from_data(data=f.read(), mime_type="image/jpeg")
        
    with open(translated_image_path, "rb") as f:
        img_trad = Part.from_data(data=f.read(), mime_type="image/jpeg")

    prompt = [
        f"Sei un ispettore di Controllo Qualità Visiva (QA) e Linguistica. Stiamo valutando l'impaginazione di un'infografica che DOVEVA essere tradotta in {target_lang}.",
        "Immagine 1 (Originale in ITALIANO):", img_orig,
        "Immagine 2 (Traduzione generata dal sistema da valutare):", img_trad,
        
        "COMPITO 1 (LAYOUT): Verifica che i testi tradotti nell'Immagine 2 NON si sovrappongano assolutamente a icone, loghi, bollini, illustrazioni o bordi della pagina.",
        "COMPITO 2 (INTEGRITÀ): Verifica che i blocchi di testo originali siano stati effettivamente sostituiti e che non ci siano antiestetici 'buchi' bianchi o cancellazioni errate sui loghi.",
        "COMPITO 3 (TRADUZIONE - CRITICO): L'Immagine 2 DEVE essere nella lingua target. Controlla tutti i testi grandi descrittivi (es. 'SENZA SOSTANZE CHIMICHE'). Se vedi che sono rimasti nella lingua originale (Italiano) e non sono stati tradotti, devi TASSATIVAMENTE bocciare l'immagine!",
        
        "ESITO: Se l'Immagine 2 è leggibile, pulita, priva di collisioni E totalmente tradotta, restituisci status 'ok'. Se c'è anche un solo testo non tradotto, o una sovrapposizione, restituisci status 'ko'.",
        "RAGIONAMENTO: Scrivi una descrizione precisa. Se bocci l'immagine per mancata traduzione, scrivi esplicitamente: 'Il testo X non è stato tradotto ed è rimasto in lingua originale'.",
        
        "Restituisci SOLO un JSON valido strutturato esattamente in questo modo:",
        "{\n  \"status\": \"ok\",\n  \"ragionamento\": \"Spiegazione dettagliata del controllo visivo e linguistico...\"\n}"
    ]

    model = GenerativeModel("gemini-3.6-flash") 
    
    max_retries = 3
    response = None
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt, 
                generation_config={"response_mime_type": "application/json"}
            )
            break  
        except ResourceExhausted as e:
            if attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1) 
                print(f"⚠️ [Agente QA] Quota esaurita (429). Ritento tra {wait_time} secondi... (Tentativo {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print("❌ Errore 429 persistente nell'Agente QA.")
                raise e  

    if not response:
        raise Exception("Errore inaspettato: Impossibile generare risposta dal QA.")

    try:
        risultato = json.loads(response.text)
    except json.JSONDecodeError:
        print("⚠️ Errore di decodifica JSON dall'Agente QA. Fallback a KO.")
        risultato = {"status": "ko", "ragionamento": "Errore interno: parsing JSON fallito."}
    
    if risultato.get("status") == "ko":
        print(f"❌ IMMAGINE SCARTATA! L'Agente QA ha bloccato la pubblicazione.")
        print(f"Motivo: {risultato.get('ragionamento')}")
    else:
        print(f"✅ IMMAGINE APPROVATA! Vaglio di qualità superato.")

    return risultato