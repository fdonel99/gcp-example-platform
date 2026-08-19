import os
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
            if p.get("bold", False):
                parole_formattate.append(f"**{testo_parola}**")
            else:
                parole_formattate.append(testo_parola)
                
        frase = " ".join(parole_formattate)
        dizionario_testi[blocco["id_blocco"]] = frase

    prompt = [
        "Sei un analista visivo e Art Director. Il tuo compito è stabilire quali testi tradurre e quali ignorare in un'infografica."
    ]

    # --- INIEZIONE DELL'IMMAGINE DI ESEMPIO (FEW-SHOT VISIVO) ---
    dir_corrente = os.path.dirname(os.path.abspath(__file__))
    esempio_path = os.path.join(dir_corrente, "esempio_infografica.jpg")
    
    if os.path.exists(esempio_path):
        with open(esempio_path, "rb") as f:
            esempio_part = Part.from_data(data=f.read(), mime_type="image/jpeg")
        prompt.extend([
            "\n--- ESEMPIO DI RIFERIMENTO PER LA REGOLA DEI BOLLINI ---",
            esempio_part,
            "Guarda bene questo esempio didattico: il testo 'NO Chemicals' è inciso DENTRO il bollino a forma di foglia verde (questo è un testo da ignorare). Al contrario, il testo 'SENZA SOSTANZE CHIMICHE' è posizionato all'esterno, DI FIANCO al bollino (questo NON fa parte del bollino e va assolutamente estratto per la traduzione). Usa questa stessa logica categorica per l'immagine che devi analizzare ora.",
            "--------------------------------------------------------\n"
        ])
    else:
        print("⚠️ File 'esempio_infografica.jpg' non trovato. Continuo senza esempio visivo.")

    # --- INIEZIONE DELL'IMMAGINE REALE DA ANALIZZARE ---
    with open(image_path, "rb") as f:
        image_part = Part.from_data(data=f.read(), mime_type="image/jpeg")

    prompt.extend([
        "Ora passa al tuo vero incarico. Immagine da analizzare:",
        image_part,
        f"Testi OCR pre-formattati dell'immagine qui sopra:\n{json.dumps(dizionario_testi, ensure_ascii=False)}",
        
        "COMPITO 1: Inserisci in 'ids_da_ignorare' ESCLUSIVAMENTE i testi incisi dentro loghi, bollini o badge. Come visto nell'esempio, i testi grandi scritti all'esterno e di fianco a un bollino NON vanno ignorati!",
        "COMPITO 2: Inserisci in 'ids_originali' i testi descrittivi da tradurre. Assicurati di includere sempre i testi scritti a fianco dei bollini.",
        
        "COMPITO 3: Restituisci il testo fuso in MARKDOWN usando i doppi asterischi (**) per il grassetto e '\\n' per gli a capo. Applica gli asterischi SOLO alle parole visivamente in grassetto nell'immagine.",
        "COMPITO 4: Assegna un RUOLO scegliendo rigorosamente tra: 'Titolo' (per i testi grandi in evidenza), 'Callout' (per i brevi testi descrittivi vicino alle icone) oppure 'Paragrafo' (per i testi lunghi e discorsivi).",
        "COMPITO 5 (ALLINEAMENTO PARAGRAFO - CRITICO): Osserva come sono incolonnate le righe. Restituisci 'centro' nella maggior parte dei casi per i callout sotto le icone."
    ])
    
    if istruzioni_correttive:
        prompt.append(f"\n⚠️ ISTRUZIONI CRITICHE E TASSATIVE DAL DIRETTORE: {istruzioni_correttive}")
        prompt.append("MODIFICA la tua analisi per obbedire in modo rigoroso a queste istruzioni.")

    prompt.append("\nRestituisci SOLO un JSON valido strutturato così:\n{\n  \"ragionamento\": \"Spiegazione...\",\n  \"ids_da_ignorare\": [4, 5],\n  \"blocchi_validi\": [\n    {\"ids_originali\": [0, 1], \"ruolo\": \"Callout\", \"testo_markdown\": \"**TESTO**\\nNormale\", \"allineamento\": \"sinistra\"}\n  ]\n}")

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