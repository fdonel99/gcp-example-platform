import os
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
    
    prompt = [
        f"Sei un ispettore di Controllo Qualità Visiva (QA) e Linguistica. Stiamo valutando l'impaginazione di un'infografica che DOVEVA essere tradotta in {target_lang}."
    ]

    # --- INIEZIONE DELL'IMMAGINE DI ESEMPIO (FEW-SHOT VISIVO) ---
    dir_corrente = os.path.dirname(os.path.abspath(__file__))
    esempio_path = os.path.join(dir_corrente, "esempio_infografica.jpg")
    
    if os.path.exists(esempio_path):
        with open(esempio_path, "rb") as f:
            esempio_part = Part.from_data(data=f.read(), mime_type="image/jpeg")
        prompt.extend([
            "\n--- ESEMPIO DIDATTICO SULLE ECCEZIONI DI TRADUZIONE ---",
            esempio_part,
            "In questa immagine di esempio, il testo 'NO Chemicals' (che si trova fisicamente DENTRO il bollino verde) è un'eccezione e deve restare in lingua originale. Invece, la dicitura 'SENZA SOSTANZE CHIMICHE' è testo esterno e DEVE obbligatoriamente essere tradotta. Usa questo rigoroso metro di giudizio per l'ispezione che stai per fare.",
            "-------------------------------------------------------\n"
        ])

    # --- INIEZIONE DELLE IMMAGINI DA VALUTARE ---
    with open(original_image_path, "rb") as f:
        img_orig = Part.from_data(data=f.read(), mime_type="image/jpeg")
        
    with open(translated_image_path, "rb") as f:
        img_trad = Part.from_data(data=f.read(), mime_type="image/jpeg")

    prompt.extend([
        "Immagine 1 (Infografica Originale):", img_orig,
        "Immagine 2 (Traduzione generata dal sistema da valutare rigorosamente):", img_trad,
        
        "COMPITO 1 (LAYOUT E COLLISIONI): Verifica che i testi tradotti nell'Immagine 2 NON si sovrappongano a loghi o bordi. Se l'ultima riga invade un logo, boccia l'immagine con 'ko'.",
        "COMPITO 2 (INTEGRITÀ): Verifica che i blocchi di testo originali siano stati sostituiti senza lasciare 'buchi' bianchi sui loghi.",
        
        "COMPITO 3 (TRADUZIONE E LE SUE ECCEZIONI - CRITICO): Come visto nell'esempio, i testi disposti a cerchio e i testi letteralmente ALL'INTERNO dei loghi (es. la scritta interna alla foglia) DEVONO RESTARE IN ORIGINALE.",
        "⚠️ ATTENZIONE PERÒ: I testi normali scritti all'esterno e DI FIANCO a un bollino (come la grande scritta a destra della foglia verde) NON fanno parte dell'eccezione e DEVONO ESSERE TRADOTTI. Se noti che un testo esterno posizionato di fianco a un logo è rimasto in italiano, BOCCIA CATEGORICAMENTE l'immagine con 'ko'.",
        
        "ESITO: Se l'Immagine 2 è pulita e i testi principali (esterni ai loghi) sono tradotti, restituisci status 'ok'. Restituisci 'ko' se c'è collisione o se un testo a fianco di un logo non è stato tradotto.",
        "RAGIONAMENTO: Scrivi una descrizione precisa del motivo del KO (es: 'Il testo di fianco al bollino verde è rimasto in italiano').",
        
        "Restituisci SOLO un JSON valido strutturato esattamente in questo modo:",
        "{\n  \"status\": \"ok\",\n  \"ragionamento\": \"Spiegazione dettagliata...\"\n}"
    ])

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
                time.sleep(wait_time)
            else:
                raise e  

    if not response:
        raise Exception("Errore inaspettato: Impossibile generare risposta dal QA.")

    try:
        risultato = json.loads(response.text)
    except json.JSONDecodeError:
        risultato = {"status": "ko", "ragionamento": "Errore interno: parsing JSON fallito."}
    
    if risultato.get("status") == "ko":
        print(f"❌ IMMAGINE SCARTATA DAL QA: {risultato.get('ragionamento')}")
    else:
        print(f"✅ IMMAGINE APPROVATA DAL QA!")

    return risultato