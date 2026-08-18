import json
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Configurazione Vertex AI
PROJECT_ID = "cloud-platform-northstar-test"
LOCATION_VERTEX = "europe-west1" # Inserisci la tua region Vertex (spesso europe-west1 o us-central1)

# Inizializza il client di Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION_VERTEX)

def analizza_e_filtra(image_path, json_estratti):
    print(f"\n🧠 Innesco Agente 1 (gemini-3.6-flash) per l'analisi visiva...")
    
    # 1. Prepariamo il dizionario semplificato {ID: Testo} per l'LLM
    dizionario_testi = {}
    for blocco in json_estratti:
        # Uniamo le parole in una singola frase leggibile per l'ID corrente
        frase = " ".join([p["testo"] for p in blocco["parole"]])
        dizionario_testi[blocco["id_blocco"]] = frase

    # 2. Carichiamo l'immagine come Part
    with open(image_path, "rb") as f:
        image_part = Part.from_data(data=f.read(), mime_type="image/jpeg")

    # 3. Il Prompt (Il tuo prompt originale + l'aggiunta dei ruoli)
    prompt = [
        "Sei un analista visivo e Art Director. Hai in input l'immagine di un'infografica e i frammenti di testo estratti tramite OCR (Formato -> ID: Testo).",
        image_part,
        f"Testi OCR:\n{json.dumps(dizionario_testi, ensure_ascii=False)}",
        "Il tuo COMPITO VITALE è duplice:",
        "COMPITO 1: Individuare gli ID dei testi che NON DEVONO ASSOLUTAMENTE ESSERE MODIFICATI o coperti da sfondi rettangolari.",
        "Inserisci nella lista 'ids_da_ignorare' TUTTI gli ID che corrispondono a queste 3 categorie:",
        "1. TESTI SULLA CONFEZIONE FISICA: Tutto ciò che è stampato direttamente sulla confezione fisica dei prodotti fotografati (bottiglie, scatole, buste). Ignorali sempre, anche se sono leggibili (es. 'Save the Bees', 'Crema', 'Miele').",
        "2. BADGE E ICONE CIRCOLARI: Tutte le piccole scritte che compongono icone o sigilli grafici (es. 'NO Chemicals', 'Animal friendly', 'Dermatologicamente testato', 'Senza parabeni', 'Riciclabile 100%', 'Siliconi'). Scartali sempre.",
        "3. ARTEFATTI E NUMERI ISOLATI causati dall'OCR.",
        "ATTENZIONE CRITICA: NON SCARTARE le scritte grandi, normali e leggibili che si trovano semplicemente ACCANTO ai badge! Ad esempio, se vedi un piccolo logo e di fianco una frase descrittiva, devi ignorare SOLO il piccolo logo. La frase descrittiva è una caratteristica che DEVE ESSERE TRADOTTA e NON deve essere scartata.",
        "ATTENZIONE 2: NON SCARTARE MAI i riquadri testuali, i titoli o i fumetti informativi esterni ai prodotti. Quelli vanno sempre tradotti.",
        "COMPITO 2: Assegna un RUOLO a tutti gli ID dell'elenco (sia quelli da ignorare che quelli da tradurre).",
        "I ruoli possibili sono: 'Titolo', 'Paragrafo', 'Badge_Logo', 'Packaging', 'Sconosciuto'.",
        "Restituisci SOLO un JSON valido strutturato esattamente in questo modo:",
        "{\n  \"ragionamento\": \"Spiega cosa vedi nei cerchi, sui prodotti e accanto ai badge\",\n  \"ids_da_ignorare\": [4, 5, 6, 7],\n  \"ruoli\": [\n    {\"id_blocco\": 0, \"ruolo\": \"Titolo\"},\n    {\"id_blocco\": 4, \"ruolo\": \"Packaging\"}\n  ]\n}"
    ]

    # Inizializziamo il modello richiesto
    model = GenerativeModel("gemini-3.6-flash") 
    
    # Forziamo l'output in formato JSON
    response = model.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    
    # Decodifichiamo il JSON stringa restituito dall'AI in un dizionario Python
    return json.loads(response.text)