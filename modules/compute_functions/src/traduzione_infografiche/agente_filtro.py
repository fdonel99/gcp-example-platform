import json
import time
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.api_core.exceptions import ResourceExhausted

PROJECT_ID = "cloud-platform-northstar-test"
LOCATION_VERTEX = "global" 
vertexai.init(project=PROJECT_ID, location=LOCATION_VERTEX)

def analizza_e_filtra(image_path, json_estratti, istruzioni_correttive=None):
    if istruzioni_correttive:
        print(f"\n🧠 Innesco Agente 1 (Filtro) - MODALITÀ CORREZIONE IN CORSO...")
    else:
        print(f"\n🧠 Innesco Agente 1 (Filtro) - Analisi Base...")
        
    dizionario_testi = {}
    for blocco in json_estratti:
        parole_formattate = []
        for p in blocco["parole"]:
            testo_parola = p["testo"]
            # FIX: Traduciamo la rilevazione OCR del grassetto direttamente in Markdown!
            if p.get("bold", False):
                parole_formattate.append(f"**{testo_parola}**")
            else:
                parole_formattate.append(testo_parola)
                
        # Creiamo la frase (es: "**EMISSIONI** **VARIABILI** SONICHE")
        frase = " ".join(parole_formattate)
        dizionario_testi[blocco["id_blocco"]] = frase

    with open(image_path, "rb") as f:
        image_part = Part.from_data(data=f.read(), mime_type="image/jpeg")

    prompt = [
        "Sei un analista visivo e Art Director. Hai in input l'immagine di un'infografica e i testi estratti dall'OCR.",
        image_part,
        f"Testi OCR pre-formattati:\n{json.dumps(dizionario_testi, ensure_ascii=False)}",
        
        "COMPITO 1: Inserisci in 'ids_da_ignorare' i testi di loghi, bollini o badge.",
        "COMPITO 2: Inserisci in 'ids_originali' i testi descrittivi da tradurre.",
        "COMPITO 3: Restituisci il testo fuso in MARKDOWN usando i doppi asterischi (**) per il grassetto e '\\n' per gli a capo. ATTENZIONE (CRITICO): Nel JSON di input potresti trovare dei doppi asterischi (**) messi a caso o del tutto assenti. NON fidarti del JSON! Guarda l'immagine: applica i doppi asterischi SOLO E SOLTANTO alle parole che tu vedi visivamente scritte con un font più spesso/grassetto. Se il JSON ha messo asterischi su parole che nell'immagine sono sottili, rimuovili. Se il JSON li ha dimenticati su titoli spessi, aggiungili tu. Sii una spietata guardia di controllo visivo!",
        "COMPITO 4: Assegna un RUOLO ('Titolo' o 'Callout').",
        
        "COMPITO 5 (ALLINEAMENTO PARAGRAFO - CRITICO): Osserva attentamente come sono incolonnate le righe di testo tra di loro (la giustificazione). "
        "1) Se le righe formano un margine dritto sul lato DESTRO (e seghettato a sinistra), restituisci 'destra'. Questo accade tipicamente per i testi nella metà SINISTRA dell'immagine, che 'puntano' verso il prodotto centrale. "
        "2) Se le righe formano un margine dritto a SINISTRA, restituisci 'sinistra'. "
        "3) Se le righe sono perfettamente centrate, restituisci 'centro'."
    ]
    
    # --- INIEZIONE DELL'ORDINE DEL DIRETTORE ---
    if istruzioni_correttive:
        prompt.append(f"⚠️ ISTRUZIONI CRITICHE E TASSATIVE DAL DIRETTORE: {istruzioni_correttive}")
        prompt.append("MODIFICA la tua analisi per obbedire in modo rigoroso a queste istruzioni e correggere il precedente errore di layout.")

    prompt.append("Restituisci SOLO un JSON valido strutturato così:\n{\n  \"ragionamento\": \"Spiegazione...\",\n  \"ids_da_ignorare\": [4, 5],\n  \"blocchi_validi\": [\n    {\"ids_originali\": [0, 1], \"ruolo\": \"Callout\", \"testo_markdown\": \"**TESTO**\\nNormale\", \"allineamento\": \"sinistra\"}\n  ]\n}")

    model = GenerativeModel("gemini-3.6-flash") 
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return json.loads(response.text)
        except ResourceExhausted as e:
            if attempt < max_retries - 1:
                time.sleep(60)
            else:
                raise e