import os
import io
import json
import textwrap
from datetime import datetime
import functions_framework
from google.cloud import storage
from google.cloud import vision
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import cv2
import html
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Inizializza i client
PROJECT_ID = "cloud-platform-northstar"
REGION = "europe-west1"
OUTPUT_BUCKET_NAME = "bkt-infografica-output"

storage_client = storage.Client()
vision_client = vision.ImageAnnotatorClient()

# Inizializza Vertex AI per Gemini
vertexai.init(project=PROJECT_ID, location=REGION)
gemini_model = GenerativeModel("gemini-2.5-flash")

def estrai_testo_da_blocco(block):
    testo = ""
    for paragraph in block.paragraphs:
        for word in paragraph.words:
            for symbol in word.symbols:
                testo += symbol.text
                if hasattr(symbol.property, 'detected_break'):
                    break_type = symbol.property.detected_break.type_
                    if break_type in [1, 2]:
                        testo += " "
                    elif break_type in [3, 5]:
                        testo += "\n"
    return testo.strip()

def formatta_vertici(vertices):
    return [{"x": v.x, "y": v.y} for v in vertices]

def estrai_colore_sfondo(img_cv, vertici):
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x = max(0, min(xs))
        min_y = max(0, min(ys))
        
        # Campiona un pixel 5px fuori dal testo per prendere lo sfondo
        y_bg = max(0, min_y - 5)
        x_bg = max(0, min_x - 5)
        bg_color = img_cv[y_bg, x_bg]
        return (int(bg_color[2]), int(bg_color[1]), int(bg_color[0]))
    except Exception:
        return (232, 106, 33) 

def estrai_colore_testo(img_cv, vertici):
    """Usa K-Means (Machine Learning) per separare accuratamente il colore del testo dallo sfondo a colori."""
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = max(0, min(xs)), max(xs)
        min_y, max_y = max(0, min(ys)), max(ys)
        
        crop = img_cv[min_y:max_y, min_x:max_x]
        if crop.size == 0: return (255, 255, 255)
            
        # Rimodella l'immagine in una lista di pixel RGB
        pixels = crop.reshape((-1, 3)).astype(np.float32)
        
        # Cerca i 2 colori dominanti (Sfondo e Testo)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, 2, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        centers = np.uint8(centers)
        counts = np.bincount(labels.flatten())
        
        # Il testo è quasi sempre il gruppo con meno pixel nel riquadro
        text_cluster_idx = np.argmin(counts)
        color = centers[text_cluster_idx]
        
        return (int(color[2]), int(color[1]), int(color[0]))
    except Exception as e:
        print(f"Errore estrazione colore testo: {e}")
        return (255, 255, 255)

def analizza_e_traduci_con_gemini(image_bytes, mime_type, dizionario_testi):
    """
    Usa Gemini per classificare i testi E tradurli contestualmente all'immagine,
    forzando un output JSON strutturato.
    """
    target_image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
    percorso_esempio = os.path.join(os.path.dirname(__file__), "esempio_infografica.jpg")
    
    try:
        with open(percorso_esempio, "rb") as f:
            esempio_bytes = f.read()
        example_image_part = Part.from_data(data=esempio_bytes, mime_type="image/jpeg")
    except FileNotFoundError:
        print("ATTENZIONE: File 'esempio_infografica.jpg' non trovato.")
        example_image_part = None

    contenuto_prompt = [
        "Sei un grafico esperto in localizzazione e un traduttore professionista. Il tuo compito è classificare i testi di un'infografica in tre categorie e tradurre quelli rilevanti tenendo sempre in considerazione il contesto dell'immagine (es. se è un cosmetico, usa termini adatti).",
    ]

    if example_image_part:
        contenuto_prompt.extend([
            "=== INIZIO ESEMPIO DI RIFERIMENTO ===",
            example_image_part,
            "Regole derivate da questo esempio:\n"
            "- 'banner': Il testo principale posizionato all'interno della grande fascia colorata a tinta unita (es. 'PER COCCOLARE LA TUA PELLE DOPO IL SOLE').\n"
            "- 'sottotitolo': Testo informativo o promozionale secondario, scritto in modo lineare e dritto (es. 'NEL RISPETTO DELLA NATURA' dentro il cerchio).\n"
            "- 'da_ignorare': Testi stampati fisicamente sul prodotto (es. 'Bee it', 'SAVE THE BEES') e testi decorativi scritti in circolo attorno alle icone (es. 'DERMATOLOGICAMENTE TESTATO').\n"
            "=== FINE ESEMPIO DI RIFERIMENTO ===\n\n"
        ])

    contenuto_prompt.extend([
        "Analizza questa NUOVA infografica applicando rigorosamente le logiche dell'esempio visivo per la classificazione, e traduci i testi approvati:",
        target_image_part,
        "Ecco i testi estratti (ID: Testo):",
        f"{json.dumps(dizionario_testi, ensure_ascii=False)}",
        "\nPer i testi classificati come 'banner' o 'sottotitolo', valuta se visivamente appaiono in grassetto (grassetto: true o false).",
        "Devi restituire SOLO un JSON valido con questa esatta struttura, includendo le traduzioni contestualizzate in inglese (en), francese (fr), tedesco (de), spagnolo (es) e olandese (nl):",
        "{\"banner\": [{\"id\": 1, \"grassetto\": true, \"traduzioni\": {\"en\": \"...\", \"fr\": \"...\", \"de\": \"...\", \"es\": \"...\", \"nl\": \"...\"}}], \"sottotitolo\": [{\"id\": 2, \"grassetto\": false, \"traduzioni\": {\"en\": \"...\", \"fr\": \"...\", \"de\": \"...\", \"es\": \"...\", \"nl\": \"...\"}}], \"da_ignorare\": [3]}"
    ])
    
    response = gemini_model.generate_content(
        contenuto_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    return json.loads(response.text.strip())

def sovrascrivi_testo(image_bytes, mappatura_testi, lingua, formato_img="JPEG"):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    font_path_regular = "montserrat.ttf"
    font_path_bold = "montserrat-bold.ttf"

    # FASE 1: Toppe di sfondo (Invariata)
    for blocco in mappatura_testi:
        testo = blocco[f"testo_tradotto_{lingua}"]
        if not testo: continue
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        colore_sfondo = tuple(blocco.get("colore_sfondo", (232, 106, 33)))
        pad = 6
        draw.rectangle([min_x - pad, min_y - pad, max_x + pad, max_y + pad], fill=colore_sfondo)

    # FASE 2: Scrittura Testi
    for blocco in mappatura_testi:
        testo = blocco[f"testo_tradotto_{lingua}"]
        if not testo: continue
        
        if blocco.get("maiuscolo", False):
            testo = testo.upper()
            
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        
        box_width = max_x - min_x
        box_height = max_y - min_y
        
        # ESPANSIONE DINAMICA: Permettiamo al testo di sbordare un po' se le parole sono lunghe
        # I titoli (banner) possono espandersi molto di più in larghezza
        tolleranza_w = 1.6 if blocco.get("tipo") == "banner" else 1.2
        tolleranza_h = 1.5
        max_allowed_width = box_width * tolleranza_w
        max_allowed_height = box_height * tolleranza_h
        
        colore_testo = tuple(blocco.get("colore_testo", (255, 255, 255)))
        
        # FORZATURA GRASSETTO: Se il testo era in maiuscolo, lo forziamo in grassetto
        # altrimenti risulterebbe illeggibile sui badge piccoli.
        is_bold = blocco.get("grassetto", False) or blocco.get("maiuscolo", False)
        current_font_path = font_path_bold if is_bold else font_path_regular
        
        font_size = 65
        min_font_size = 14 # Alzato a 14 per mantenere leggibilità
        testo_adattato = testo
        font_scelto = None
        
        while font_size >= min_font_size:
            try: font = ImageFont.truetype(current_font_path, font_size)
            except IOError: break

            avg_char_width = font.getlength("a") or 1
            chars_per_line = max(1, int(max_allowed_width / avg_char_width))
            
            # BREAK_LONG_WORDS=FALSE impedisce che parole come "FEUCHTIGKEITSSPENDEND" vengano spezzate a metà
            testo_splittato = textwrap.fill(testo, width=chars_per_line, break_long_words=False)
            
            bbox = draw.multiline_textbbox((0, 0), testo_splittato, font=font, align="center")
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            
            # Verifichiamo contro i confini espansi, non contro la scatola originale stretta
            if text_w <= max_allowed_width and text_h <= max_allowed_height:
                testo_adattato = testo_splittato
                font_scelto = font
                break
            font_size -= 2
            
        if not font_scelto:
            try: font_scelto = ImageFont.truetype(current_font_path, min_font_size)
            except IOError: font_scelto = ImageFont.load_default()
            avg_char_width = font_scelto.getlength("a") or 1
            testo_adattato = textwrap.fill(testo, width=max(1, int(max_allowed_width / avg_char_width)), break_long_words=False)

        bbox = draw.multiline_textbbox((0, 0), testo_adattato, font=font_scelto, align="center")
        final_w, final_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        # La centratura usa ancora box_width originale, così il testo cresce dal centro verso l'esterno
        x_pos = min_x + (box_width - final_w) / 2 - bbox[0]
        y_pos = min_y + (box_height - final_h) / 2 - bbox[1]
        
        draw.multiline_text((x_pos, y_pos), testo_adattato, fill=colore_testo, font=font_scelto, align="center")
        
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format=formato_img)
    return img_byte_arr.getvalue()


@functions_framework.cloud_event
def process_infographic_trigger(cloud_event):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    if file_name.endswith("/"): return
    if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): return

    try:
        nome_base, estensione = os.path.splitext(file_name)
        formato_img = "PNG" if estensione.lower() == ".png" else "JPEG"
        mime_type = "image/png" if formato_img == "PNG" else "image/jpeg"
        
        source_bucket = storage_client.bucket(bucket_name)
        source_blob = source_bucket.blob(file_name)
        
        original_image_bytes = source_blob.download_as_bytes()
        nparr = np.frombuffer(original_image_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 1. OCR Iniziale
        gcs_uri = f"gs://{bucket_name}/{file_name}"
        image = vision.Image(source=vision.ImageSource(gcs_image_uri=gcs_uri))
        text_response = vision_client.document_text_detection(image=image)
        
        if text_response.error.message:
            raise Exception(f"Errore Vision API: {text_response.error.message}")

        # 2. Estrazione Testi con ID numerico
        testi_vision = {}
        blocchi_vision = []
        if text_response.full_text_annotation:
            for id_blocco, block in enumerate(text_response.full_text_annotation.pages[0].blocks):
                testo = estrai_testo_da_blocco(block)
                if testo:
                    testi_vision[id_blocco] = testo
                    blocchi_vision.append((id_blocco, block, testo))
        
        mappatura_testi = []
        
        # 3. Chiamata a Gemini per Classificazione E Traduzione Semantica
        print("Interrogazione Gemini in corso...")
        if testi_vision:
            classificazione_gemini = analizza_e_traduci_con_gemini(original_image_bytes, mime_type, testi_vision)
            
            # Gestione sicura del JSON esteso
            info_traduzione = {}
            for cat in ["banner", "sottotitolo"]:
                lista_raw = classificazione_gemini.get(cat, [])
                for item in lista_raw:
                    if isinstance(item, dict) and "id" in item:
                        try:
                            id_pulito = int(item["id"])
                            info_traduzione[id_pulito] = {
                                "tipo": cat, 
                                "grassetto": item.get("grassetto", False),
                                "traduzioni": item.get("traduzioni", {})
                            }
                        except ValueError:
                            continue
                            
            ids_da_tradurre = list(info_traduzione.keys())
            print(f"Gemini ha elaborato e tradotto gli ID: {ids_da_tradurre}")
            
            # 4. Processamento ed Estrazione Dati solo per gli ID approvati
            for id_blocco, block, testo_originale in blocchi_vision:
                if id_blocco not in ids_da_tradurre:
                    continue
                    
                vertici = formatta_vertici(block.bounding_box.vertices)
                colore_sfondo = estrai_colore_sfondo(img_cv, vertici)
                colore_testo = estrai_colore_testo(img_cv, vertici)
                
                metadati = info_traduzione[id_blocco]
                is_bold = metadati["grassetto"]
                tipo_testo = metadati["tipo"]
                traduzioni_gemini = metadati["traduzioni"]
                is_upper = testo_originale.isupper() 
                
                # Salviamo le traduzioni restituite da Gemini (applicando unescape di sicurezza)
                traduzioni_finali = {}
                for lang in ["en", "fr", "de", "es", "nl"]:
                    testo_tradotto = traduzioni_gemini.get(lang, testo_originale) # Fallback sul testo originale se manca
                    traduzioni_finali[lang] = html.unescape(testo_tradotto)
                
                mappatura_testi.append({
                    "testo_originale": testo_originale,
                    "testo_tradotto_en": traduzioni_finali["en"],
                    "testo_tradotto_fr": traduzioni_finali["fr"],
                    "testo_tradotto_de": traduzioni_finali["de"],
                    "testo_tradotto_es": traduzioni_finali["es"], 
                    "testo_tradotto_nl": traduzioni_finali["nl"], 
                    "vertici_blocco": vertici,
                    "colore_sfondo": colore_sfondo,
                    "colore_testo": colore_testo,
                    "grassetto": is_bold,
                    "maiuscolo": is_upper,
                    "tipo": tipo_testo
                })
        
        destination_bucket = storage_client.bucket(OUTPUT_BUCKET_NAME)
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        output_image_name_it = f"elaborato_{current_date_str}/{nome_base}_it{estensione}"
        source_bucket.copy_blob(source_blob, destination_bucket, new_name=output_image_name_it)
        
        json_blob = destination_bucket.blob(f"elaborato_{current_date_str}/{nome_base}_metadati.json")
        json_blob.upload_from_string(
            data=json.dumps(mappatura_testi, indent=2, ensure_ascii=False),
            content_type='application/json'
        )

        print("Sovrascrittura nativa dei testi tradotti...")
        content_type = source_blob.content_type if source_blob.content_type else f'image/{formato_img.lower()}'
        
        for lang in ["en", "fr", "de", "es", "nl"]:
            if mappatura_testi:
                final_image_bytes = sovrascrivi_testo(original_image_bytes, mappatura_testi, lang, formato_img)
            else:
                final_image_bytes = original_image_bytes
                
            clean_blob_name = f"elaborato_{current_date_str}/{nome_base}_{lang}{estensione}"
            clean_blob = destination_bucket.blob(clean_blob_name)
            clean_blob.upload_from_string(final_image_bytes, content_type=content_type)

        print("Tutto completato con successo.")

    except Exception as e:
        print(f"Errore critico: {e}")
        raise e