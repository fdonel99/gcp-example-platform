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
        min_x, max_x = max(0, min(xs)), min(img_cv.shape[1] - 1, max(xs))
        min_y, max_y = max(0, min(ys)), min(img_cv.shape[0] - 1, max(ys))
        
        # Campiona i pixel lungo il perimetro, 4px fuori dal testo
        pad = 4
        bordi = []
        
        # Bordo superiore e inferiore
        for x in range(min_x, max_x + 1, max(1, (max_x - min_x) // 10)):
            if min_y - pad >= 0: bordi.append(img_cv[min_y - pad, x])
            if max_y + pad < img_cv.shape[0]: bordi.append(img_cv[max_y + pad, x])
            
        # Bordo sinistro e destro
        for y in range(min_y, max_y + 1, max(1, (max_y - min_y) // 10)):
            if min_x - pad >= 0: bordi.append(img_cv[y, min_x - pad])
            if max_x + pad < img_cv.shape[1]: bordi.append(img_cv[y, max_x + pad])
            
        if bordi:
            # La mediana ignora elementi grafici di disturbo
            bg_color = np.median(bordi, axis=0)
            return (int(bg_color[2]), int(bg_color[1]), int(bg_color[0]))
            
        return (255, 255, 255)
    except Exception:
        return (232, 106, 33)

def estrai_colore_testo(img_cv, vertici, colore_sfondo):
    """K-Means k=3 per superare l'anti-aliasing dei font sottili."""
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = max(0, min(xs)), max(xs)
        min_y, max_y = max(0, min(ys)), max(ys)
        
        crop = img_cv[min_y:max_y, min_x:max_x]
        if crop.size == 0: return (50, 50, 50)
            
        pixels = crop.reshape((-1, 3)).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        
        # Cerchiamo 3 colori (Sfondo, Sfumatura Bordo, Cuore del Testo)
        _, _, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        
        # Identifica il colore più distante e opposto rispetto allo sfondo
        bg_bgr = np.array([colore_sfondo[2], colore_sfondo[1], colore_sfondo[0]], dtype=np.float32)
        max_dist = -1
        best_color = centers[0]
        
        for center in centers:
            dist = np.linalg.norm(center.astype(np.float32) - bg_bgr)
            if dist > max_dist:
                max_dist = dist
                best_color = center
                
        return (int(best_color[2]), int(best_color[1]), int(best_color[0]))
    except Exception as e:
        print(f"Errore colore testo: {e}")
        return (50, 50, 50)

def rileva_allineamento(block):
    """Calcola geometricamente se un blocco di testo è allineato a sx, dx o centro."""
    linee = []
    linea_corrente = []
    
    for paragraph in block.paragraphs:
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
        return "center"
        
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

def analizza_e_traduci_con_gemini(image_bytes, mime_type, dizionario_testi):
    target_image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
    percorso_esempio = os.path.join(os.path.dirname(__file__), "esempio_infografica.jpg")
    
    try:
        with open(percorso_esempio, "rb") as f:
            esempio_bytes = f.read()
        example_image_part = Part.from_data(data=esempio_bytes, mime_type="image/jpeg")
    except FileNotFoundError:
        example_image_part = None

    contenuto_prompt = [
        "Sei un grafico esperto in localizzazione e un traduttore professionista. Il tuo compito è classificare i testi di un'infografica e tradurre quelli rilevanti tenendo in considerazione il contesto visivo.",
    ]

    if example_image_part:
        contenuto_prompt.extend([
            "=== INIZIO ESEMPIO DI RIFERIMENTO ===",
            example_image_part,
            "Regole derivate da questo esempio:\n"
            "- 'banner': Il testo principale posizionato all'interno della grande fascia colorata.\n"
            "- 'sottotitolo': Testo informativo o promozionale secondario.\n"
            "- 'da_ignorare': Testi stampati fisicamente sul prodotto o dentro badge colorati.\n"
            "=== FINE ESEMPIO DI RIFERIMENTO ===\n\n"
        ])

    contenuto_prompt.extend([
        "Analizza questa NUOVA infografica.",
        target_image_part,
        "Ecco i testi estratti (ID: Testo):",
        f"{json.dumps(dizionario_testi, ensure_ascii=False)}",
        "\nREGOLE TASSATIVE (IL MANCATO RISPETTO CAUSERÀ IL CRASH):",
        "1. NON OMETTERE NESSUN ID. Ogni ID originale estratto deve esistere nel JSON finale.",
        "2. INSERISCI IN 'da_ignorare' loghi isolati o grafiche (es. 'NO Chemicals'). NON unirli mai ad altri testi.",
        "3. SCARTI: Se un ID contiene il testo del logo fuso per errore con quello tradotto, metti la parola intrusa nell'array 'scarti'.",
        "4. TRADUZIONE CONTESTUALE DISTRIBUITA (FONDAMENTALE): Leggi gli ID adiacenti per comprendere il senso grammaticale completo (es. ID 1: 'EMISSIONI', ID 2: 'SONICHE'). Elabora la traduzione corretta ('VARIABLE SONIC EMISSIONS'). Infine, DISTRIBUISCI le parole tradotte nei rispettivi ID originali per mantenere l'impaginazione (es. ID 1: 'VARIABLE SONIC', ID 2: 'EMISSIONS').",
        "5. MANTIENI I PESI VISIVI: Distribuisci le parole in base alla lunghezza e al grassetto. Se un ID originale aveva poche parole ma grandi/in grassetto, inserisci le parole chiave della traduzione in quell'ID.",
        "6. EVITA LE STRINGHE VUOTE: Non unire le traduzioni in un solo ID lasciando gli altri vuoti (\"\"). Spalma sempre le parole della traduzione attraverso gli ID che componevano la frase originale.",
        "7. ATTENZIONE AL GRASSETTO: Imposta 'grassetto': true se c'è ALMENO UNA parola visibilmente in grassetto in quel blocco.",
        "Restituisci SOLO il JSON valido:",
        "{\"banner\": [], \"sottotitolo\": [{\"id\": 0, \"grassetto\": true, \"scarti\": [], \"traduzioni\": {\"en\": \"...\"}}], \"da_ignorare\": [4]}"
    ])
    
    response = gemini_model.generate_content(
        contenuto_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text.strip())

def sovrascrivi_testo(image_bytes, mappatura_testi, lingua, formato_img="JPEG"):
    import copy 
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    font_path_regular = "montserrat.ttf"
    font_path_bold = "montserrat-bold.ttf"
    mappatura_locale = copy.deepcopy(mappatura_testi)

    print(f"\n--- LOGICA SOVRASCRITTURA TESTO [{lingua.upper()}] ---")

    blocchi_attivi = []
    blocchi_vuoti = []
    
    for blocco in mappatura_locale:
        testo = blocco.get(f"testo_tradotto_{lingua}", "")
        if not testo or str(testo).strip() == "":
            blocchi_vuoti.append(blocco)
        else:
            blocchi_attivi.append(blocco)
            
    # Fase di unione spazi vuoti mantenuta per sicurezza (anche se mitigata dal prompt distribuito)
    for vuoto in blocchi_vuoti:
        if not blocchi_attivi: continue
        
        vx, vy = [v['x'] for v in vuoto["vertici_blocco"]], [v['y'] for v in vuoto["vertici_blocco"]]
        cx_v, cy_v = sum(vx) / len(vx), sum(vy) / len(vy)
        
        blocco_vicino = None
        min_dist = float('inf')
        
        for attivo in blocchi_attivi:
            ax, ay = [v['x'] for v in attivo["vertici_blocco"]], [v['y'] for v in attivo["vertici_blocco"]]
            cx_a, cy_a = sum(ax) / len(ax), sum(ay) / len(ay)
            
            h_a = max(1, max(ay) - min(ay))
            tolleranza = h_a * 2.5
            dist = ((cx_v - cx_a)**2 + (cy_v - cy_a)**2)**0.5
            
            if dist < min_dist and dist < tolleranza:
                min_dist = dist
                blocco_vicino = attivo
                
        if blocco_vicino:
            blocco_vicino["vertici_blocco"].extend(vuoto["vertici_blocco"])
            testo_orig_vicino = str(blocco_vicino.get("testo_originale", "")).strip()
            testo_orig_vuoto = str(vuoto.get("testo_originale", "")).strip()
            blocco_vicino["testo_originale"] = f"{testo_orig_vicino} {testo_orig_vuoto}".strip()

    # REVERSE-ENGINEERING DEL FONT ORIGINALE
    for blocco in blocchi_attivi:
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        box_w = max(xs) - min(xs)
        box_h = max(ys) - min(ys)
        
        testo_orig = str(blocco.get("testo_originale", "")).strip()
        align_mode = blocco.get("allineamento", "center")
        
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
            
            testo_lineare = testo_orig.replace("\n", " ") 
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
        print(f"ID Elaborato: Testo=['{testo_orig[:15]}...'] | Max_Font={blocco['tetto_massimo_font']} | Grassetto={is_bold} | Align={align_mode}")

    # TOPPE DI SFONDO
    for blocco in mappatura_locale:
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        colore_sfondo = tuple(blocco.get("colore_sfondo", (232, 106, 33)))
        pad = 6
        draw.rectangle([min_x - pad, min_y - pad, max_x + pad, max_y + pad], fill=colore_sfondo)

    # SCRITTURA TESTI TRADOTTI
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
        align_mode = blocco.get("allineamento", "center")
        
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
        
        # Calcola la X in base all'allineamento
        if align_mode == "left":
            x_pos = min_x - bbox[0]
        elif align_mode == "right":
            x_pos = max_x - final_w - bbox[0]
        else:
            x_pos = min_x + (box_width - final_w) / 2 - bbox[0]
            
        y_pos = min_y + (box_height - final_h) / 2 - bbox[1]
        
        draw.multiline_text((x_pos, y_pos), testo_adattato, fill=colore_testo, font=font_scelto, align=align_mode)
        print(f"Stampa '{testo[:15]}...' -> Font Render Size: {font_size} | Colore (RGB): {colore_testo}")
        
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

    print(f"=== INIZIO ELABORAZIONE: {file_name} ===")

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
        print("Richiesta testi OCR a Google Vision...")
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
                    print(f"Vision ID {id_blocco}: {testo[:30]}...")
        
        mappatura_testi = []
        
        # 3. Chiamata a Gemini per Classificazione E Traduzione Semantica
        print("\nInterrogazione Traduzione Semantica in corso...")
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
                                "scarti": item.get("scarti", []),
                                "traduzioni": item.get("traduzioni", {})
                            }
                        except ValueError:
                            continue
                            
            ids_da_tradurre = list(info_traduzione.keys())
            print(f"Gemini IDs Approvati: {ids_da_tradurre}")
            
            # 4. Processamento ed Estrazione Dati solo per gli ID approvati
            for id_blocco, block, testo_originale in blocchi_vision:
                if id_blocco not in ids_da_tradurre:
                    continue
                
                metadati = info_traduzione[id_blocco]
                scarti = metadati.get("scarti", [])
                
                # --- LOGICA: COSTRUZIONE BOUNDING BOX CHIRURGICA ---
                xs = []
                ys = []
                
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        testo_parola = "".join([s.text for s in word.symbols])
                        
                        # Escludiamo le coordinate se la parola è negli scarti di Gemini
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
                    vertici = formatta_vertici(block.bounding_box.vertices)
                # ---------------------------------------------------------
                    
                colore_sfondo = estrai_colore_sfondo(img_cv, vertici)
                colore_testo = estrai_colore_testo(img_cv, vertici, colore_sfondo)
                allineamento_originale = rileva_allineamento(block)
                
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
                print(f"Colore Sfondo ID {id_blocco}: {colore_sfondo} | Colore Testo: {colore_testo}")
        
        destination_bucket = storage_client.bucket(OUTPUT_BUCKET_NAME)
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        output_image_name_it = f"elaborato_{current_date_str}/{nome_base}_it{estensione}"
        source_bucket.copy_blob(source_blob, destination_bucket, new_name=output_image_name_it)
        
        json_blob = destination_bucket.blob(f"elaborato_{current_date_str}/{nome_base}_metadati.json")
        json_blob.upload_from_string(
            data=json.dumps(mappatura_testi, indent=2, ensure_ascii=False),
            content_type='application/json'
        )

        print("\nSovrascrittura nativa dei testi tradotti...")
        content_type = source_blob.content_type if source_blob.content_type else f'image/{formato_img.lower()}'
        
        for lang in ["en", "fr", "de", "es", "nl"]:
            if mappatura_testi:
                final_image_bytes = sovrascrivi_testo(original_image_bytes, mappatura_testi, lang, formato_img)
            else:
                final_image_bytes = original_image_bytes
                
            clean_blob_name = f"elaborato_{current_date_str}/{nome_base}_{lang}{estensione}"
            clean_blob = destination_bucket.blob(clean_blob_name)
            clean_blob.upload_from_string(final_image_bytes, content_type=content_type)

        print("\n=== ELABORAZIONE COMPLETATA CON SUCCESSO ===")

    except Exception as e:
        print(f"Errore critico: {e}")
        raise e