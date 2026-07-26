import os
import io
import json
import textwrap
from datetime import datetime
import functions_framework
from google.cloud import storage
from google.cloud import vision
from google.cloud import translate_v2 as translate
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Inizializza i client
PROJECT_ID = "cloud-platform-northstar"
REGION = "europe-west1"
OUTPUT_BUCKET_NAME = "bkt-infografica-output"

storage_client = storage.Client()
vision_client = vision.ImageAnnotatorClient()
translate_client = translate.Client()

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
    """Estrae il colore medio dei pixel che compongono il testo usando una maschera di contrasto."""
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = max(0, min(xs)), max(xs)
        min_y, max_y = max(0, min(ys)), max(ys)
        
        crop = img_cv[min_y:max_y, min_x:max_x]
        if crop.size == 0: return (255, 255, 255)
            
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        white_pixels = cv2.countNonZero(thresh)
        black_pixels = thresh.size - white_pixels
        
        if white_pixels < black_pixels:
            text_mask = thresh
        else:
            text_mask = cv2.bitwise_not(thresh)
            
        mean_color = cv2.mean(crop, mask=text_mask)
        return (int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))
    except Exception as e:
        print(f"Errore estrazione colore testo: {e}")
        return (255, 255, 255)

def analizza_con_gemini(image_bytes, mime_type, dizionario_testi):
    """
    Usa Gemini in modalità Multimodal Few-Shot Prompting.
    Costringe l'API a rispondere esclusivamente con un JSON strutturato.
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
        "Sei un grafico esperto in localizzazione. Il tuo compito è classificare i testi di un'infografica in tre categorie.",
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
        "Analizza questa NUOVA infografica applicando rigorosamente le logiche dell'esempio visivo:",
        target_image_part,
        "Ecco i testi estratti (ID: Testo):",
        f"{json.dumps(dizionario_testi, ensure_ascii=False)}",
        "\nPer i testi classificati come 'banner' o 'sottotitolo', valuta se visivamente appaiono in grassetto (grassetto: true o false).",
        "Devi restituire SOLO un JSON valido con questa esatta struttura:",
        "{\"banner\": [{\"id\": 1, \"grassetto\": true}], \"sottotitolo\": [{\"id\": 2, \"grassetto\": false}], \"da_ignorare\": [3]}"
    ])
    
    # Obblighiamo Vertex AI a restituire un JSON pulito
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

    for blocco in mappatura_testi:
        testo = blocco[f"testo_tradotto_{lingua}"]
        if not testo: continue
        
        # 1. Applicazione automatica del maiuscolo
        if blocco.get("maiuscolo", False):
            testo = testo.upper()
            
        vertici = blocco["vertici_blocco"]
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        box_width = max_x - min_x
        box_height = max_y - min_y
        
        colore_sfondo = tuple(blocco.get("colore_sfondo", (232, 106, 33)))
        colore_testo = tuple(blocco.get("colore_testo", (255, 255, 255)))
        is_bold = blocco.get("grassetto", False)
        current_font_path = font_path_bold if is_bold else font_path_regular
        pad = 6
        
        # 2. Toppa localizzata per coprire il vecchio testo
        draw.rectangle([min_x - pad, min_y - pad, max_x + pad, max_y + pad], fill=colore_sfondo)
        
        font_size = 65
        min_font_size = 12
        testo_adattato = testo
        font_scelto = None
        
        while font_size >= min_font_size:
            try: 
                font = ImageFont.truetype(current_font_path, font_size)
            except IOError:
                font = ImageFont.load_default()
                font_scelto = font
                break

            avg_char_width = font.getlength("a") or 1
            chars_per_line = max(1, int(box_width / avg_char_width))
            testo_splittato = textwrap.fill(testo, width=chars_per_line)
            
            bbox = draw.multiline_textbbox((0, 0), testo_splittato, font=font, align="center")
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            
            if text_w <= box_width and text_h <= box_height:
                testo_adattato = testo_splittato
                font_scelto = font
                break
            font_size -= 2
            
        if not font_scelto:
            try: font_scelto = ImageFont.truetype(current_font_path, min_font_size)
            except: font_scelto = ImageFont.load_default()
            testo_adattato = textwrap.fill(testo, width=max(1, int(box_width / 8)))

        # 3. Disegno e Centratura Ottica Compensata
        bbox = draw.multiline_textbbox((0, 0), testo_adattato, font=font_scelto, align="center")
        final_w = bbox[2] - bbox[0]
        final_h = bbox[3] - bbox[1]
        
        # Sottraiamo bbox[0] e bbox[1] per eliminare i margini invisibili del font
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
        
        # 3. Chiamata a Gemini per la Classificazione Semantica
        print("Interrogazione Gemini in corso...")
        if testi_vision:
            classificazione_gemini = analizza_con_gemini(original_image_bytes, mime_type, testi_vision)
            
            # Gestione sicura e cast degli ID a interi
            info_traduzione = {}
            for cat in ["banner", "sottotitolo"]:
                lista_raw = classificazione_gemini.get(cat, [])
                for item in lista_raw:
                    if isinstance(item, dict) and "id" in item:
                        try:
                            # FORZATURA A NUMERO INTERO
                            id_pulito = int(item["id"])
                            info_traduzione[id_pulito] = {
                                "tipo": cat, 
                                "grassetto": item.get("grassetto", False)
                            }
                        except ValueError:
                            continue
                    elif isinstance(item, (int, str)): # Fallback se Gemini formatta male
                        try:
                            info_traduzione[int(item)] = {
                                "tipo": cat,
                                "grassetto": False
                            }
                        except ValueError:
                            continue
                            
            ids_da_tradurre = list(info_traduzione.keys())
            print(f"Gemini ha autorizzato la traduzione per gli ID: {ids_da_tradurre}")
            
            # 4. Processamento ed Estrazione Dati solo per gli ID approvati
            for id_blocco, block, testo_originale in blocchi_vision:
                if id_blocco not in ids_da_tradurre:
                    print(f"Skipped (Ignorato da Gemini): {testo_originale[:15]}...")
                    continue
                    
                vertici = formatta_vertici(block.bounding_box.vertices)
                colore_sfondo = estrai_colore_sfondo(img_cv, vertici)
                colore_testo = estrai_colore_testo(img_cv, vertici)
                
                # Otteniamo i metadati stabiliti da Gemini e dal codice Python
                metadati = info_traduzione[id_blocco]
                is_bold = metadati["grassetto"]
                tipo_testo = metadati["tipo"]
                is_upper = testo_originale.isupper() # Rilevamento automatico Python
                
                traduzioni = {}
                for lang in ["en", "fr", "de", "es", "nl"]:
                    trad = translate_client.translate(testo_originale, target_language=lang)
                    traduzioni[lang] = trad["translatedText"]
                
                mappatura_testi.append({
                    "testo_originale": testo_originale,
                    "testo_tradotto_en": traduzioni["en"],
                    "testo_tradotto_fr": traduzioni["fr"],
                    "testo_tradotto_de": traduzioni["de"],
                    "testo_tradotto_es": traduzioni["es"], 
                    "testo_tradotto_nl": traduzioni["nl"], 
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