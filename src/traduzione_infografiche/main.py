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

# ==========================================
# GESTORE LOG PER IL BUCKET
# ==========================================
class BucketLogger:
    def __init__(self):
        self.logs = []
    
    def log(self, messaggio):
        timestamp = datetime.now().strftime("%H:%M:%S")
        riga = f"[{timestamp}] {messaggio}"
        print(riga) 
        self.logs.append(riga)
        
    def get_testo_completo(self):
        return "\\n".join(self.logs)

# ==========================================

def estrai_testo_da_paragrafo(paragraph):
    testo = ""
    for word in paragraph.words:
        for symbol in word.symbols:
            testo += symbol.text
            if hasattr(symbol.property, 'detected_break'):
                break_type = symbol.property.detected_break.type_
                if break_type in [1, 2]:
                    testo += " "
                elif break_type in [3, 5]:
                    testo += "\\n"
    return testo.strip()

def formatta_vertici(vertices):
    return [{"x": v.x, "y": v.y} for v in vertices]

def estrai_colore_sfondo(img_cv, vertici):
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = max(0, min(xs)), min(img_cv.shape[1] - 1, max(xs))
        min_y, max_y = max(0, min(ys)), min(img_cv.shape[0] - 1, max(ys))
        
        pad = 4
        bordi = []
        
        for x in range(min_x, max_x + 1, max(1, (max_x - min_x) // 10)):
            if min_y - pad >= 0: bordi.append(img_cv[min_y - pad, x])
            if max_y + pad < img_cv.shape[0]: bordi.append(img_cv[max_y + pad, x])
            
        for y in range(min_y, max_y + 1, max(1, (max_y - min_y) // 10)):
            if min_x - pad >= 0: bordi.append(img_cv[y, min_x - pad])
            if max_x + pad < img_cv.shape[1]: bordi.append(img_cv[y, max_x + pad])
            
        if bordi:
            bg_color = np.median(bordi, axis=0)
            return (int(bg_color[2]), int(bg_color[1]), int(bg_color[0]))
            
        return (255, 255, 255)
    except Exception:
        return (232, 106, 33)

def estrai_colore_testo(img_cv, vertici, colore_sfondo, logger):
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = max(0, min(xs)), max(xs)
        min_y, max_y = max(0, min(ys)), max(ys)
        
        crop = img_cv[min_y:max_y, min_x:max_x]
        if crop.size == 0: return (50, 50, 50)
            
        pixels = crop.reshape((-1, 3)).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        
        _, _, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        
        bg_lum = 0.299 * colore_sfondo[2] + 0.587 * colore_sfondo[1] + 0.114 * colore_sfondo[0]
        best_color = centers[0]
        
        if bg_lum > 127:
            min_lum = float('inf')
            for center in centers:
                lum = 0.299 * center[2] + 0.587 * center[1] + 0.114 * center[0]
                if lum < min_lum:
                    min_lum = lum
                    best_color = center
        else:
            max_lum = -1
            for center in centers:
                lum = 0.299 * center[2] + 0.587 * center[1] + 0.114 * center[0]
                if lum > max_lum:
                    max_lum = lum
                    best_color = center
                    
        return (int(best_color[2]), int(best_color[1]), int(best_color[0]))
    except Exception as e:
        logger.log(f"Errore colore testo: {e}")
        return (50, 50, 50)

def rileva_allineamento(paragraph):
    linee = []
    linea_corrente = []
    
    for word in paragraph.words:
        xs = [v.x for v in word.bounding_box.vertices]
        linea_corrente.append({"min_x": min(xs), "max_x": max(xs)})
        
        if any(hasattr(s.property, 'detected_break') and s.property.detected_break.type_ in [3, 5] for s in word.symbols):
            linee.append(linea_corrente)
            linea_corrente = []
            
    if linea_corrente:
        linee.append(linea_corrente)
        
    linee = [l for l in linee if l] 
    
    if len(linee) <= 1:
        return "left"
        
    left_margins = [l[0]["min_x"] for l in linee]
    center_margins = [(l[0]["min_x"] + l[-1]["max_x"]) / 2 for l in linee]
    right_margins = [l[-1]["max_x"] for l in linee]
    
    diff_left = max(left_margins) - min(left_margins)
    diff_center = max(center_margins) - min(center_margins)
    diff_right = max(right_margins) - min(right_margins)
    
    min_diff = min(diff_left, diff_center, diff_right)
    
    if min_diff == diff_left and diff_left <= 30:
        return "left"
    elif min_diff == diff_right and diff_right <= 30:
        return "right"
    else:
        return "center"

def analizza_e_traduci_con_gemini(image_bytes, mime_type, dizionario_testi, logger):
    logger.log("\\n--- INIZIO ELABORAZIONE GEMINI ---")
    target_image_part = Part.from_data(data=image_bytes, mime_type=mime_type)

    contenuto_prompt = [
        "Sei un grafico esperto in localizzazione. Il tuo compito è classificare e tradurre i testi di questa infografica.",
        target_image_part,
        "Ecco i testi estratti (ID: Testo):",
        f"{json.dumps(dizionario_testi, ensure_ascii=False)}",
        "\\nREGOLE TASSATIVE (IL MANCATO RISPETTO CAUSERÀ IL CRASH DEL SISTEMA):",
        "1. TRADUCI NELLE 5 LINGUE: en, fr, de, es, nl.",
        "2. NON OMETTERE NESSUN ID. Ogni ID estratto deve esistere nel JSON.",
        "3. SCARTI E LOGHI (CRITICO): Se un ID contiene una parola inglese intrusa appartenente al disegno di un logo (es. la parola 'Chemicals' nell'ID 'Chemicals CHIMICHE'), DEVI isolare 'Chemicals' nell'array 'scarti' e tradurre solo il resto del testo. Se non lo fai, il programma cancellerà il logo originale!",
        "4. TRADUZIONE STRICT 1:1 (CRITICO): Non unire MAI le frasi e non spostare le parole tra un ID e l'altro! Devi tradurre ogni singolo ID per quello che contiene, in modo letterale. Il layout geometrico dipende da questo.",
        "   - Es. Se ID 0 è 'EMISSIONI VARIABILI', restituisci 'VARIABLE EMISSIONS'.",
        "   - Es. Se ID 1 è 'SONICHE', restituisci 'SONIC'.",
        "   - NON FARE l'errore di mettere 'VARIABLE SONIC' nell'ID 0 e 'EMISSIONS' nell'ID 1. Distruggeresti le dimensioni dei font!",
        "5. ATTENZIONE AL GRASSETTO: Imposta 'grassetto': true se c'è ALMENO UNA parola visibilmente in grassetto in quel frammento.",
        "Restituisci SOLO un JSON valido strutturato così:",
        '{"banner": [], "sottotitolo": [{"id": 0, "grassetto": true, "scarti": [], "traduzioni": {"en": "...", "fr": "...", "de": "...", "es": "...", "nl": "..."}}], "da_ignorare": [4]}'
    ]
    
    logger.log("Invio richiesta a Gemini 2.5 Flash...")
    response = gemini_model.generate_content(
        contenuto_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    risultato_testo = response.text.strip()
    logger.log(f">>> RAW JSON DA GEMINI:\\n{risultato_testo}")
    logger.log("--- FINE ELABORAZIONE GEMINI ---\\n")
    return json.loads(risultato_testo)

def sovrascrivi_testo(image_bytes, mappatura_testi, lingua, logger, formato_img="JPEG"):
    import copy 
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    font_path_regular = "montserrat.ttf"
    font_path_bold = "montserrat-bold.ttf"
    mappatura_locale = copy.deepcopy(mappatura_testi)

    logger.log(f"\\n--- AVVIO DISEGNO TESTO LINGUA: [{lingua.upper()}] ---")

    blocchi_attivi = []
    
    for blocco in mappatura_locale:
        testo = blocco.get(f"testo_tradotto_{lingua}", "")
        logger.log(f"[{lingua.upper()}] ID Originale: '{blocco.get('testo_originale')[:20]}...' -> Traduzione Ricevuta: '{testo}'")
        if testo and str(testo).strip() != "":
            blocchi_attivi.append(blocco)
            
    for blocco in blocchi_attivi:
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        box_w = max(xs) - min(xs)
        box_h = max(ys) - min(ys)
        
        testo_orig = str(blocco.get("testo_originale", "")).strip()
        align_mode = blocco.get("allineamento", "left")
        
        if not testo_orig:
            blocco["tetto_massimo_font"] = 65
            continue
            
        is_bold = blocco.get("grassetto", False) or blocco.get("maiuscolo", False)
        current_font_path = font_path_bold if is_bold else font_path_regular
        
        sim_font_size = 80
        best_font_size = 12
        
        while sim_font_size >= 12:
            try: font = ImageFont.truetype(current_font_path, sim_font_size)
            except IOError: break
            
            testo_lineare = testo_orig.replace("\\n", " ") 
            avg_char_width = font.getlength("a") or 1
            chars_per_line = max(1, int(box_w / avg_char_width))
            
            testo_splittato = textwrap.fill(testo_lineare, width=chars_per_line, break_long_words=False)
            bbox = draw.multiline_textbbox((0, 0), testo_splittato, font=font, align=align_mode)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            
            if tw <= box_w and th <= box_h:
                best_font_size = sim_font_size
                break
                
            sim_font_size -= 2
            
        blocco["tetto_massimo_font"] = int(best_font_size * 1.05)

    for blocco in mappatura_locale:
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        colore_sfondo = tuple(blocco.get("colore_sfondo", (232, 106, 33)))
        pad = 6
        draw.rectangle([min_x - pad, min_y - pad, max_x + pad, max_y + pad], fill=colore_sfondo)

    for blocco in mappatura_locale:
        testo = blocco.get(f"testo_tradotto_{lingua}", "")
        if not testo or str(testo).strip() == "": 
            continue
        
        if blocco.get("maiuscolo", False):
            testo = str(testo).upper()
            
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        
        box_width = max_x - min_x
        box_height = max_y - min_y
        max_allowed_width = box_width * 1.05
        max_allowed_height = box_height * 1.2
        
        testo_pulito = testo.replace("-", " ").replace(".", "").replace(",", "")
        ha_parole_chiave_maiuscole = any(w.isupper() and len(w) > 2 for w in testo_pulito.split())
        
        is_bold = blocco.get("grassetto", False) or blocco.get("maiuscolo", False) or ha_parole_chiave_maiuscole
        colore_testo = tuple(blocco.get("colore_testo", (255, 255, 255)))
        current_font_path = font_path_bold if is_bold else font_path_regular
        align_mode = blocco.get("allineamento", "left") 
        
        tetto_massimo_font = blocco.get("tetto_massimo_font", 65)
        font_size = min(65, tetto_massimo_font) 
        
        min_font_size = 12 
        testo_adattato = testo
        font_scelto = None
        
        while font_size >= min_font_size:
            try: font = ImageFont.truetype(current_font_path, font_size)
            except IOError: break

            avg_char_width = font.getlength("a") or 1
            chars_per_line = max(1, int(max_allowed_width / avg_char_width))
            
            testo_splittato = textwrap.fill(testo, width=chars_per_line, break_long_words=False)
            bbox = draw.multiline_textbbox((0, 0), testo_splittato, font=font, align=align_mode)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            
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

        bbox = draw.multiline_textbbox((0, 0), testo_adattato, font=font_scelto, align=align_mode)
        final_w, final_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        if align_mode == "left":
            x_pos = min_x - bbox[0]
        elif align_mode == "right":
            x_pos = max_x - final_w - bbox[0]
        else:
            x_pos = min_x + (box_width - final_w) / 2 - bbox[0]
            
        y_pos = min_y + (box_height - final_h) / 2 - bbox[1]
        
        draw.multiline_text((x_pos, y_pos), testo_adattato, fill=colore_testo, font=font_scelto, align=align_mode)
        
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format=formato_img)
    logger.log(f"--- FINE DISEGNO TESTO LINGUA: [{lingua.upper()}] ---\\n")
    return img_byte_arr.getvalue()


@functions_framework.cloud_event
def process_infographic_trigger(cloud_event):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    if file_name.endswith("/"): return
    if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): return

    logger = BucketLogger()
    logger.log(f"=== INIZIO ELABORAZIONE: {file_name} ===")

    try:
        nome_base, estensione = os.path.splitext(file_name)
        formato_img = "PNG" if estensione.lower() == ".png" else "JPEG"
        mime_type = "image/png" if formato_img == "PNG" else "image/jpeg"
        
        source_bucket = storage_client.bucket(bucket_name)
        source_blob = source_bucket.blob(file_name)
        
        original_image_bytes = source_blob.download_as_bytes()
        nparr = np.frombuffer(original_image_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        logger.log("\\n--- RICHIESTA OCR (Google Vision) ---")
        gcs_uri = f"gs://{bucket_name}/{file_name}"
        image = vision.Image(source=vision.ImageSource(gcs_image_uri=gcs_uri))
        text_response = vision_client.document_text_detection(image=image)
        
        if text_response.error.message:
            raise Exception(f"Errore Vision API: {text_response.error.message}")

        testi_vision = {}
        blocchi_vision = []
        id_counter = 0 
        
        if text_response.full_text_annotation:
            for page in text_response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        testo = estrai_testo_da_paragrafo(paragraph)
                        if testo:
                            testi_vision[id_counter] = testo
                            blocchi_vision.append((id_counter, paragraph, testo))
                            logger.log(f"Vision ID {id_counter}: {testo[:40]}...")
                            id_counter += 1
        
        mappatura_testi = []
        
        if testi_vision:
            classificazione_gemini = analizza_e_traduci_con_gemini(original_image_bytes, mime_type, testi_vision, logger)
            
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
                                "scarti": item.get("scarti", []),
                                "traduzioni": item.get("traduzioni", {})
                            }
                        except ValueError:
                            continue
                            
            ids_da_tradurre = list(info_traduzione.keys())
            logger.log(f">>> Gemini IDs Approvati per la traduzione: {ids_da_tradurre}")
            
            for id_blocco, paragraph, testo_originale in blocchi_vision:
                if id_blocco not in ids_da_tradurre:
                    continue
                
                metadati = info_traduzione[id_blocco]
                scarti = metadati.get("scarti", [])
                
                xs = []
                ys = []
                
                for word in paragraph.words:
                    testo_parola = "".join([s.text for s in word.symbols])
                    
                    if testo_parola not in scarti:
                        for v in word.bounding_box.vertices:
                            xs.append(v.x)
                            ys.append(v.y)
                
                if xs and ys:
                    vertici = [
                        {"x": min(xs), "y": min(ys)}, {"x": max(xs), "y": min(ys)},
                        {"x": max(xs), "y": max(ys)}, {"x": min(xs), "y": max(ys)}
                    ]
                else:
                    vertici = formatta_vertici(paragraph.bounding_box.vertices)
                    
                colore_sfondo = estrai_colore_sfondo(img_cv, vertici)
                colore_testo = estrai_colore_testo(img_cv, vertici, colore_sfondo, logger)
                allineamento_originale = rileva_allineamento(paragraph)
                
                is_bold = metadati["grassetto"]
                tipo_testo = metadati["tipo"]
                traduzioni_gemini = metadati["traduzioni"]
                is_upper = testo_originale.isupper() 
                
                traduzioni_finali = {}
                for lang in ["en", "fr", "de", "es", "nl"]:
                    if lang in traduzioni_gemini:
                        testo_tradotto = traduzioni_gemini[lang]
                    else:
                        testo_tradotto = testo_originale 
                        
                    if isinstance(testo_tradotto, str) and testo_tradotto.strip() != "":
                        traduzioni_finali[lang] = html.unescape(testo_tradotto)
                    else:
                        traduzioni_finali[lang] = ""
                
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
                    "tipo": tipo_testo,
                    "allineamento": allineamento_originale
                })
        
        destination_bucket = storage_client.bucket(OUTPUT_BUCKET_NAME)
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        percorso_base_output = f"elaborato_{current_date_str}"
        
        output_image_name_it = f"{percorso_base_output}/{nome_base}_it{estensione}"
        source_bucket.copy_blob(source_blob, destination_bucket, new_name=output_image_name_it)
        
        json_blob = destination_bucket.blob(f"{percorso_base_output}/{nome_base}_metadati.json")
        json_blob.upload_from_string(
            data=json.dumps(mappatura_testi, indent=2, ensure_ascii=False),
            content_type='application/json'
        )

        content_type = source_blob.content_type if source_blob.content_type else f'image/{formato_img.lower()}'
        
        for lang in ["en", "fr", "de", "es", "nl"]:
            if mappatura_testi:
                final_image_bytes = sovrascrivi_testo(original_image_bytes, mappatura_testi, lang, logger, formato_img)
            else:
                final_image_bytes = original_image_bytes
                
            clean_blob_name = f"{percorso_base_output}/{nome_base}_{lang}{estensione}"
            clean_blob = destination_bucket.blob(clean_blob_name)
            clean_blob.upload_from_string(final_image_bytes, content_type=content_type)

        logger.log("\\n=== ELABORAZIONE COMPLETATA CON SUCCESSO ===")

    except Exception as e:
        logger.log(f"\\nERRORE CRITICO: {e}")
        raise e
    finally:
        try:
            testo_log = logger.get_testo_completo()
            percorso_log = f"elaborato_{datetime.now().strftime('%Y-%m-%d')}/{nome_base}_debug.txt"
            log_blob = destination_bucket.blob(percorso_log)
            log_blob.upload_from_string(testo_log, content_type='text/plain')
            print(f"File di log salvato con successo nel bucket come: {percorso_log}")
        except Exception as log_err:
            print(f"Impossibile salvare il file di log nel bucket: {log_err}")