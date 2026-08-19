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
        
        "COMPITO 1 (LAYOUT E COLLISIONI): Verifica che i testi tradotti nell'Immagine 2 NON si sovrappongano assolutamente a icone, loghi (incluso il logo 'Bee it' in basso), illustrazioni o bordi della pagina. Se l'ultima riga di un paragrafo invade lo spazio del logo o vi si appoggia sopra, segnalalo e boccia l'immagine con 'ko'.",
        "COMPITO 2 (INTEGRITÀ): Verifica che i blocchi di testo originali siano stati effettivamente sostituiti e che non ci siano antiestetici 'buchi' bianchi o cancellazioni errate sui loghi.",
        
        # QUI ABBIAMO AGGIUNTO L'ECCEZIONE PER IL QA
        "COMPITO 3 (TRADUZIONE E LE SUE ECCEZIONI - CRITICO): Verifica che i testi descrittivi principali, i titoli e i paragrafi siano stati tradotti. TUTTAVIA, ci sono delle ECCEZIONI ASSOLUTE: i testi disposti a cerchio (es. 'DERMATOLOGICAMENTE TESTATO', 'RICICLABILE 100%', 'SENZA PARABENI'), i bollini, i sigilli grafici e le scritte stampate fisicamente sui prodotti DEVONO RESTARE IN ITALIANO. Se noti che questi testi circolari o loghi sono rimasti in italiano, È CORRETTO COSÌ! NON bocciare l'immagine per questo motivo. Boccia l'immagine SOLO se i testi discorsivi/descrittivi esterni ai loghi sono rimasti in italiano.",
        
        "ESITO: Se l'Immagine 2 è leggibile, pulita, priva di collisioni E i testi principali sono tradotti (al netto delle eccezioni sui loghi/cerchi), restituisci status 'ok'. Restituisci 'ko' SOLO se ci sono sovrapposizioni o se un testo discorsivo/paragrafo è stato dimenticato in italiano.",
        "RAGIONAMENTO: Scrivi una descrizione precisa. Se bocci l'immagine, specifica esattamente QUALE testo descrittivo (non a cerchio) non è stato tradotto o dove si trova la sovrapposizione.",
        
        "Restituisci SOLO un JSON valido strutturato esattamente in questo modo:",
        "{\n  \"status\": \"ok\",\n  \"ragionamento\": \"Spiegazione dettagliata...\"\n}"
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