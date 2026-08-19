import json
import vertexai
from vertexai.generative_models import GenerativeModel

PROJECT_ID = "cloud-platform-northstar-test"
LOCATION_VERTEX = "global" 
vertexai.init(project=PROJECT_ID, location=LOCATION_VERTEX)

def traduci_testi(testi_markdown_da_tradurre, mappa_ruoli, lingue_target, istruzioni_correttive=None):
    if istruzioni_correttive:
         print(f"\n🌍 Innesco Agente 2 (Traduttore) - MODALITÀ CORREZIONE IN CORSO...")
    else:
         print(f"\n🌍 Innesco Agente 2 (Traduttore: {', '.join(lingue_target)})...")
         
    payload_traduzione = {}
    for id_b, testo_md in testi_markdown_da_tradurre.items():
        payload_traduzione[id_b] = {"testo_originale_md": testo_md, "ruolo": mappa_ruoli.get(id_b, "Sconosciuto")}
        
    prompt = [
        f"Sei un copywriter pubblicitario multilingua. Traduci i testi in: {', '.join(lingue_target)}.",
        
        "ATTENZIONE 1 (FEDELTÀ MARKDOWN - REGOLA D'ORO): Il tuo compito è ricalcare ESATTAMENTE i doppi asterischi (**) presenti nell'originale. Se l'originale ha parole tra asterischi, applicali sulle parole tradotte equivalenti. Se l'originale NON ha asterischi, È SEVERAMENTE VIETATO aggiungerli di tua iniziativa.",
        
        "ATTENZIONE 2 (SINTESI E SPAZI): Sii CONCISO. Le traduzioni inutilmente lunghe rompono l'equilibrio della grafica.",
        
        "ATTENZIONE 3 (STRUTTURA RIGHE E A CAPO - CRITICO): Per evitare collisioni con loghi o elementi grafici vicini, la tua traduzione DEVE mantenere lo stesso numero di righe e la stessa impaginazione dell'originale. Se il testo originale contiene il carattere '\\n', inseriscilo obbligatoriamente nella traduzione nel punto logico corrispondente, spezzando la frase nello stesso modo.",
        
        f"Testi da tradurre:\n{json.dumps(payload_traduzione, ensure_ascii=False)}"
    ]
    
    # --- INIEZIONE DELL'ORDINE DEL DIRETTORE ---
    if istruzioni_correttive:
        prompt.append(f"⚠️ ISTRUZIONI CRITICHE E TASSATIVE DAL DIRETTORE: {istruzioni_correttive}")
        prompt.append("Applica rigorosamente questa istruzione sulla formattazione/scelta delle parole.")

    prompt.append("Restituisci SOLO un JSON valido strutturato così:\n{\n  \"traduzioni\": [\n    {\n      \"id_blocco\": 0,\n      \"testi_tradotti\": {\n        \"en\": \"Testo normale\\n**TESTO IN GRASSETTO**\"\n      }\n    }\n  ]\n}")

    model = GenerativeModel("gemini-3.6-flash") 
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)