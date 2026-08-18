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
        "ATTENZIONE 1 (FORMATTAZIONE MARKDOWN CRITICA): Devi preservare rigorosamente il grassetto originale utilizzando gli asterischi doppi (**). Se il testo originale italiano ha delle parole tra asterischi, la tua traduzione DEVE obbligatoriamente avere gli asterischi attorno alle parole equivalenti.",
        "ATTENZIONE 2 (SINTESI): Sii CONCISO. Evita traduzioni inutilmente lunghe che potrebbero rompere il layout grafico.",
        "ATTENZIONE 3 (IMPAGINAZIONE): Se il testo originale contiene il carattere '\\n', mantienilo esattamente nel punto logico corrispondente per preservare l'impaginazione su più righe.",
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