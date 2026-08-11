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
import re
import ast
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Inizializza i client
PROJECT_ID = "cloud-platform-northstar-test"
REGION = "global"
OUTPUT_BUCKET_NAME = "bkt-infografica-output"

storage_client = storage.Client(project=PROJECT_ID)
vision_client = vision.ImageAnnotatorClient()

# Inizializza Vertex AI per Gemini
vertexai.init(project=PROJECT_ID, location=REGION)
gemini_model = GenerativeModel("gemini-3.6-flash")

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
        return "\n".join(self.logs)

# ==========================================

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
        logger.log(f"Errore colore testo: {e}")
        return (50, 50, 50)

# --- MIGLIORAMENTO: Riconoscimento spaziale per titoli e frasi a riga singola ---
def rileva_allineamento(blocchi_list, tutti_i_blocchi_valori, img_width):
    linee = []
    linea_corrente = []
    
    xs_totali = []
    for block in blocchi_list:
        for paragraph in block.paragraphs:
            for word in paragraph.words:
                xs = [v.x for v in word.bounding_box.vertices]
                xs_totali.extend(xs)
                linea_corrente.append({"min_x": min(xs), "max_x": max(xs)})
                
                if any(hasattr(s.property, 'detected_break') and s.property.detected_break.type_ in [3, 5] for s in word.symbols):
                    linee.append(linea_corrente)
                    linea_corrente = []
                
    if linea_corrente:
        linee.append(linea_corrente)
        
    linee = [l for l in linee if l] 
    
    # Se ha più di una riga, guarda se stesso (metodo classico)
    if len(linee) > 1:
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
            
    # Se è una sola riga (es. TITOLO), guarda gli altri blocchi per allinearsi a loro!
    if not xs_totali: return "left"
    my_min_x = min(xs_totali)
    my_max_x = max(xs_totali)
    my_center = (my_min_x + my_max_x) / 2
    
    left_matches = 0
    center_matches = 0
    right_matches = 0
    
    for other_b in tutti_i_blocchi_valori:
        if other_b['max_x'] - other_b['min_x'] < 10: continue
        # Esclude se stesso
        if abs(other_b['min_x'] - my_min_x) < 5 and abs(other_b['max_x'] - my_max_x) < 5:
            continue
            
        if abs(other_b['min_x'] - my_min_x) < 15:
            left_matches += 1
        if abs(other_b['max_x'] - my_max_x) < 15:
            right_matches += 1
        if abs((other_b['min_x'] + other_b['max_x'])/2 - my_center) < 15:
            center_matches += 1

    if left_matches > 0 and left_matches >= center_matches and left_matches >= right_matches:
        return "left"
    elif center_matches > 0 and center_matches >= left_matches and center_matches >= right_matches:
        return "center"
    elif right_matches > 0 and right_matches >= left_matches and right_matches >= center_matches:
        return "right"
    else:
        # Fallback estremo: coordinate assolute rispetto all'immagine
        if my_min_x < img_width * 0.3:
            return "left"
        elif my_max_x > img_width * 0.7:
            return "right"
        else:
            return "center"

def estrai_vertici_linee(blocchi_list):
    linee_vertici = []
    linea_corrente_xs = []
    linea_corrente_ys = []
    
    for block in blocchi_list:
        for paragraph in block.paragraphs:
            for word in paragraph.words:
                for v in word.bounding_box.vertices:
                    linea_corrente_xs.append(v.x)
                    linea_corrente_ys.append(v.y)
                
                if any(hasattr(s.property, 'detected_break') and s.property.detected_break.type_ in [3, 5] for s in word.symbols):
                    if linea_corrente_xs and linea_corrente_ys:
                        linee_vertici.append([
                            {"x": min(linea_corrente_xs), "y": min(linea_corrente_ys)},
                            {"x": max(linea_corrente_xs), "y": min(linea_corrente_ys)},
                            {"x": max(linea_corrente_xs), "y": max(linea_corrente_ys)},
                            {"x": min(linea_corrente_xs), "y": max(linea_corrente_ys)}
                        ])
                    linea_corrente_xs = []
                    linea_corrente_ys = []
                    
    if linea_corrente_xs and linea_corrente_ys:
        linee_vertici.append([
            {"x": min(linea_corrente_xs), "y": min(linea_corrente_ys)},
            {"x": max(linea_corrente_xs), "y": min(linea_corrente_ys)},
            {"x": max(linea_corrente_xs), "y": max(linea_corrente_ys)},
            {"x": min(linea_corrente_xs), "y": max(linea_corrente_ys)}
        ])
        
    return linee_vertici

def pulisci_e_carica_json(risultato_testo, logger):
    risultato_testo = risultato_testo.strip()
    if risultato_testo.startswith("```"):
        risultato_testo = re.sub(r'^```(json)?\n', '', risultato_testo)
        risultato_testo = re.sub(r'\n```$', '', risultato_testo)
    
    risultato_testo = risultato_testo.strip()
    risultato_testo = re.sub(r'\\(?![/"\\bfnrtu])', r'\\\\', risultato_testo)

    try:
        return json.loads(risultato_testo)
    except json.JSONDecodeError as e:
        logger.log(f"⚠️ JSONDecodeError iniziale: {e}. Tentativo di riparazione...")
        testo_riparato = re.sub(r',\s*([\]}])', r'\1', risultato_testo)
        try:
            return json.loads(testo_riparato)
        except Exception:
            pass
        try:
            testo_riparato = testo_riparato.replace("true", "True").replace("false", "False").replace("null", "None")
            risultato_ast = ast.literal_eval(testo_riparato)
            return risultato_ast
        except Exception as ast_err:
            logger.log(f"❌ Impossibile riparare il JSON. Fallimento definitivo.")
            raise e

# --- CHIAMATA AI 1: ISOLAMENTO BOX DA PROTEGGERE ---
def identifica_testi_da_ignorare(image_bytes, mime_type, dizionario_testi, logger):
    logger.log("\n--- CHIAMATA AI 1: IDENTIFICAZIONE TESTI DA IGNORARE (BADGE E LOGHI) ---")
    target_image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
    
    prompt = [
        "Sei un analista visivo. Hai in input l'immagine di un'infografica e i frammenti di testo estratti tramite OCR (Formato -> ID: Testo).",
        target_image_part,
        f"{json.dumps(dizionario_testi, ensure_ascii=False)}",
        "Il tuo COMPITO VITALE è individuare gli ID dei testi che NON DEVONO ASSOLUTAMENTE ESSERE MODIFICATI o coperti da sfondi rettangolari.",
        "Inserisci nella lista 'ids_da_ignorare' TUTTI gli ID che corrispondono a queste 3 categorie:",
        "1. TESTI SULLA CONFEZIONE FISICA: Tutto ciò che è stampato direttamente sulla confezione fisica dei prodotti fotografati (bottiglie, scatole, buste). Ignorali sempre, anche se sono leggibili (es. 'Save the Bees', 'Crema', 'Miele').",
        "2. BADGE E ICONE CIRCOLARI: Tutte le piccole scritte che compongono icone o sigilli grafici (es. 'NO Chemicals', 'Animal friendly', 'Dermatologicamente testato', 'Senza parabeni', 'Riciclabile 100%', 'Siliconi'). Scartali sempre.",
        "3. ARTEFATTI E NUMERI ISOLATI causati dall'OCR.",
        "ATTENZIONE CRITICA: NON SCARTARE le scritte grandi, normali e leggibili che si trovano semplicemente ACCANTO ai badge! Ad esempio, se vedi un piccolo logo e di fianco una frase descrittiva, devi ignorare SOLO il piccolo logo. La frase descrittiva è una caratteristica che DEVE ESSERE TRADOTTA e NON deve essere scartata.",
        "ATTENZIONE 2: NON SCARTARE MAI i riquadri testuali, i titoli o i fumetti informativi esterni ai prodotti. Quelli vanno sempre tradotti.",
        "Restituisci SOLO un JSON valido strutturato esattamente in questo modo:",
        "{\n  \"ragionamento\": \"Spiega cosa vedi nei cerchi, sui prodotti e accanto ai badge\",\n  \"ids_da_ignorare\": [4, 5, 6, 7]\n}"
    ]
    response = gemini_model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return pulisci_e_carica_json(response.text, logger)

# --- CHIAMATA AI 2: TRADUZIONE CON REGOLE MARKDOWN ---
def analizza_e_traduci_con_gemini(image_bytes, mime_type, dizionario_testi_filtrato, logger):
    logger.log("\n--- CHIAMATA AI 2: RAGGRUPPAMENTO E TRADUZIONE CON MARKDOWN ---")
    target_image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
    
    prompt = [
        "Sei un grafico esperto in localizzazione. Hai l'immagine e i testi VALIDATI dell'OCR (solo quelli da tradurre, i badge sono già stati filtrati).",
        target_image_part,
        f"{json.dumps(dizionario_testi_filtrato, ensure_ascii=False)}",
        "L'OCR spesso spezza le frasi. Guardando l'immagine, RAGGRUPPA gli ID che formano visivamente un'unica frase di senso compiuto nello stesso blocco testuale.",
        "Smistali in 'banner' (titoli e testi grandi) o 'sottotitolo' (testi descrittivi).",
        "Traduci l'intera frase in: en, fr, de, es, nl.",
        "=== REGOLA SPECIALE PER IL GRASSETTO (MARKDOWN) ===",
        "Osserva attentamente il testo originale nell'immagine. Se una o più PAROLE SPECIFICHE all'interno della frase sono scritte in GRASSETTO, con CROMIE EVIDENTI o in MAIUSCOLO per dare enfasi rispetto al resto del testo (es. 'Ad ogni acquisto... contribuisci alla creazione...'), devi identificare quali sono e applicare i doppi asterischi di Markdown (**) alle parole equivalenti nella tua traduzione.",
        "Esempio Traduzione: 'With every purchase... **you contribute to the creation**...'",
        "Se invece l'intero blocco è tutto in grassetto o tutto in stampatello, NON usare il markdown, ma imposta semplicemente la variabile 'grassetto': true nell'oggetto JSON.",
        "=== ALTRE REGOLE TASSATIVE ===",
        "1. NON OMETTERE NULLA: Devi elaborare TUTTI gli ID ricevuti in input. Controlla accuratamente i box informativi laterali e assicurati di includerli tutti nel JSON.",
        "2. NON DUPLICARE GLI ID: Ogni ID deve apparire UNA SOLA VOLTA nel JSON finale. Fai attenzione a non assegnare due traduzioni allo stesso ID.",
        "3. ASSOCIAZIONE CORRETTA: Assicurati di assegnare a ciascuna traduzione l'ID esatto (o gli ID uniti in array) corrispondente al testo originale.",
        "Restituisci SOLO un JSON valido così strutturato:",
        "{\"banner\": [{\"ids\": [0, 1], \"grassetto\": false, \"traduzioni\": {\"en\": \"Testo normale e **testo bold**\", \"fr\": \"...\", \"de\": \"...\", \"es\": \"...\", \"nl\": \"...\"}}], \"sottotitolo\": []}"
    ]
    response = gemini_model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return pulisci_e_carica_json(response.text, logger)

# ======================================================================
# MOTORE DI RENDERING PER TESTO MISTO (REGULAR/BOLD) TRAMITE MARKDOWN
# Permette a Python di "spezzare" la frase capendo quando cambiare Font
# ======================================================================
def misura_testo_misto(testo_md, max_w, font_reg, font_bold):
    parts = []
    is_bold = False
    for p in testo_md.split("**"):
        if p: parts.append((p, is_bold))
        is_bold = not is_bold

    words_data = []
    for test_frag, bld in parts:
        frag_words = re.split(r'(\s+)', test_frag)
        for w in frag_words:
            if w: words_data.append((w, bld))

    lines = []
    current_line = []
    current_line_w = 0
    max_line_w = 0
    
    for w, bld in words_data:
        font_to_use = font_bold if bld else font_reg
        w_len = font_to_use.getlength(w) if hasattr(font_to_use, 'getlength') else font_to_use.getsize(w)[0]
        
        if w.isspace() and not current_line:
            continue
            
        if current_line_w + w_len <= max_w:
            current_line.append((w, bld, w_len))
            current_line_w += w_len
        else:
            if current_line:
                lines.append(current_line)
                if current_line_w > max_line_w: max_line_w = current_line_w
            if w.isspace():
                current_line = []
                current_line_w = 0
            else:
                current_line = [(w, bld, w_len)]
                current_line_w = w_len
                
    if current_line:
        lines.append(current_line)
        if current_line_w > max_line_w: max_line_w = current_line_w

    if hasattr(font_bold, 'getbbox'):
        bbox_test = font_bold.getbbox("Ay")
        line_h = bbox_test[3] - bbox_test[1] + 2
    else:
        line_h = font_bold.getsize("Ay")[1] + 2
        
    total_h = len(lines) * line_h
    return max_line_w, total_h, lines, line_h

def disegna_testo_misto(draw, bbox_rect, lines, line_h, font_reg, font_bold, colore, align="center"):
    x_min, y_min, x_max, y_max = bbox_rect
    max_w = x_max - x_min
    total_h = len(lines) * line_h
    
    start_y = y_min + max(0, (y_max - y_min) - total_h) / 2
    current_y = start_y
    
    for line in lines:
        line_clean = line.copy()
        # Rimuove gli spazi invisibili a fine riga per un calcolo di allineamento perfetto
        while line_clean and line_clean[-1][0].isspace():
            line_clean.pop()
            
        line_w = sum([item[2] for item in line_clean])
        
        if align == "left":
            current_x = x_min
        elif align == "right":
            current_x = x_max - line_w
        else:
            current_x = x_min + (max_w - line_w) / 2
            
        # Per disegnare usiamo la riga intera in modo che disegni anche gli spazi
        for w, bld, w_len in line:
            font_to_use = font_bold if bld else font_reg
            draw.text((current_x, current_y), w, font=font_to_use, fill=colore)
            current_x += w_len
            
        current_y += line_h
# ======================================================================

def sovrascrivi_testo(image_bytes, mappatura_testi, lingua, logger, formato_img="JPEG", img_width=0):
    import copy 
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    font_path_regular = "montserrat.ttf"
    font_path_bold = "montserrat-bold.ttf"
    mappatura_locale = copy.deepcopy(mappatura_testi)

    logger.log(f"\n--- AVVIO DISEGNO TESTO LINGUA: [{lingua.upper()}] ---")

    blocchi_attivi = []
    
    for blocco in mappatura_locale:
        testo = blocco.get(f"testo_tradotto_{lingua}", "")
        logger.log(f"[{lingua.upper()}] ID fusi {blocco.get('ids_originali')}: '{blocco.get('testo_originale')[:25]}...' -> '{testo}'")
        
        testo_orig_pulito = str(blocco.get('testo_originale', '')).strip().lower()
        testo_trad_pulito = str(testo).strip().replace("**", "").lower()
        if testo and testo_trad_pulito != "" and testo_trad_pulito != testo_orig_pulito:
            blocchi_attivi.append(blocco)

    for blocco in blocchi_attivi:
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        box_w = max(xs) - min(xs)
        box_h = max(ys) - min(ys)
        
        # Pulizia momentanea dei marcatori markdown per misurare il rettangolo in modo pulito
        testo_orig = str(blocco.get("testo_originale", "")).strip()
        align_mode = blocco.get("allineamento", "center")
        
        is_bold_global = blocco.get("grassetto", False) or blocco.get("maiuscolo", False)
        current_font_path = font_path_bold if is_bold_global else font_path_regular
        
        sim_font_size = 80
        best_font_size = 12
        
        while sim_font_size >= 12:
            try: font = ImageFont.truetype(current_font_path, sim_font_size)
            except IOError: break
            
            testo_lineare = testo_orig.replace("\n", " ").replace("**", "")
            avg_char_width = font.getlength("a") if hasattr(font, 'getlength') else font.getsize("a")[0]
            chars_per_line = max(1, int(box_w / avg_char_width))
            
            testo_splittato = textwrap.fill(testo_lineare, width=chars_per_line, break_long_words=False)
            
            if hasattr(draw, 'multiline_textbbox'):
                bbox = draw.multiline_textbbox((0, 0), testo_splittato, font=font, align=align_mode)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            else:
                tw, th = draw.multiline_textsize(testo_splittato, font=font)
                
            if tw <= box_w and th <= box_h:
                best_font_size = sim_font_size
                break
                
            sim_font_size -= 2
            
        blocco["tetto_massimo_font"] = int(best_font_size * 1.05)

    # TOPPE DI SFONDO (Sfondo che si adatta alle singole righe)
    for blocco in blocchi_attivi:
        colore_sfondo = tuple(blocco.get("colore_sfondo", (232, 106, 33)))
        pad = 4 
        linee_vertici = blocco.get("linee_vertici", [blocco["vertici_blocco"]])
        
        for linea_v in linee_vertici:
            xs = [v['x'] for v in linea_v]
            ys = [v['y'] for v in linea_v]
            if not xs or not ys: continue
            min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
            draw.rectangle([min_x - pad, min_y - pad, max_x + pad, max_y + pad], fill=colore_sfondo)

    # SCRITTURA TESTI TRADOTTI
    for blocco in blocchi_attivi:
        testo = blocco.get(f"testo_tradotto_{lingua}", "")
        if blocco.get("maiuscolo", False):
            testo = str(testo).upper()
            
        vertici = blocco["vertici_blocco"]
        xs, ys = [v['x'] for v in vertici], [v['y'] for v in vertici]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        
        box_width = max_x - min_x
        box_height = max_y - min_y
        max_allowed_width = box_width * 1.03
        max_allowed_height = box_height * 1.15
        
        testo_pulito = testo.replace("-", " ").replace(".", "").replace(",", "").replace("**", "")
        ha_parole_chiave_maiuscole = any(w.isupper() and len(w) > 2 for w in testo_pulito.split())
        
        is_bold_global = blocco.get("grassetto", False) or blocco.get("maiuscolo", False) or ha_parole_chiave_maiuscole
        colore_testo = tuple(blocco.get("colore_testo", (255, 255, 255)))
        align_mode = blocco.get("allineamento", "center")
        
        tetto_massimo_font = blocco.get("tetto_massimo_font", 65)
        font_size = min(65, tetto_massimo_font) 
        min_font_size = 12 
        
        has_markdown = "**" in testo

        # GESTIONE AVANZATA (MARKDOWN - GRASSETTO MISTO)
        if has_markdown and not is_bold_global:
            while font_size >= min_font_size:
                try: 
                    font_reg = ImageFont.truetype(font_path_regular, font_size)
                    font_bold = ImageFont.truetype(font_path_bold, font_size)
                except IOError: 
                    break

                text_w, text_h, lines, line_h = misura_testo_misto(testo, max_allowed_width, font_reg, font_bold)
                if text_w <= max_allowed_width and text_h <= max_allowed_height:
                    break
                font_size -= 2
                
            if font_size < min_font_size:
                try: 
                    font_reg = ImageFont.truetype(font_path_regular, min_font_size)
                    font_bold = ImageFont.truetype(font_path_bold, min_font_size)
                except IOError: pass
                text_w, text_h, lines, line_h = misura_testo_misto(testo, max_allowed_width, font_reg, font_bold)
                
            bbox_rect = (min_x, min_y, min_x + max_allowed_width, min_y + max_allowed_height)
            disegna_testo_misto(draw, bbox_rect, lines, line_h, font_reg, font_bold, colore_testo, align=align_mode)

        # GESTIONE TRADIZIONALE (TUTTO GRASSETTO o TUTTO REGULAR)
        else:
            testo = testo.replace("**", "") 
            font_scelto = None
            testo_adattato = testo
            
            while font_size >= min_font_size:
                try: 
                    font_scelto = ImageFont.truetype(font_path_bold if is_bold_global else font_path_regular, font_size)
                except IOError: break

                avg_char_width = font_scelto.getlength("a") if hasattr(font_scelto, 'getlength') else font_scelto.getsize("a")[0]
                chars_per_line = max(1, int(max_allowed_width / avg_char_width))
                
                testo_splittato = textwrap.fill(testo, width=chars_per_line, break_long_words=False)
                
                if hasattr(draw, 'multiline_textbbox'):
                    bbox = draw.multiline_textbbox((0, 0), testo_splittato, font=font_scelto, align=align_mode)
                    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                else:
                    text_w, text_h = draw.multiline_textsize(testo_splittato, font=font_scelto)
                
                if text_w <= max_allowed_width and text_h <= max_allowed_height:
                    testo_adattato = testo_splittato
                    break
                font_size -= 2
                
            if font_size < min_font_size:
                try: font_scelto = ImageFont.truetype(font_path_bold if is_bold_global else font_path_regular, min_font_size)
                except IOError: font_scelto = ImageFont.load_default()
                avg_char_width = font_scelto.getlength("a") if hasattr(font_scelto, 'getlength') else font_scelto.getsize("a")[0]
                testo_adattato = textwrap.fill(testo, width=max(1, int(max_allowed_width / avg_char_width)), break_long_words=False)

            if hasattr(draw, 'multiline_textbbox'):
                bbox = draw.multiline_textbbox((0, 0), testo_adattato, font=font_scelto, align=align_mode)
                final_w, final_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            else:
                final_w, final_h = draw.multiline_textsize(testo_adattato, font=font_scelto)
                bbox = [0, 0, final_w, final_h]
            
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
    logger.log(f"--- FINE DISEGNO TESTO LINGUA: [{lingua.upper()}] ---\n")
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

    destination_bucket = None 
    nome_base = ""

    try:
        nome_base, estensione = os.path.splitext(file_name)
        formato_img = "PNG" if estensione.lower() == ".png" else "JPEG"
        mime_type = "image/png" if formato_img == "PNG" else "image/jpeg"
        
        destination_bucket = storage_client.bucket(OUTPUT_BUCKET_NAME) 
        source_bucket = storage_client.bucket(bucket_name)
        source_blob = source_bucket.blob(file_name)
        
        original_image_bytes = source_blob.download_as_bytes()
        nparr = np.frombuffer(original_image_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        img_width = img_cv.shape[1]
        
        logger.log("\n--- RICHIESTA OCR (Google Vision) ---")
        gcs_uri = f"gs://{bucket_name}/{file_name}"
        image = vision.Image(source=vision.ImageSource(gcs_image_uri=gcs_uri))
        text_response = vision_client.document_text_detection(image=image)
        
        if text_response.error.message:
            raise Exception(f"Errore Vision API: {text_response.error.message}")

        testi_vision = {}
        blocchi_vision = {} 
        
        if text_response.full_text_annotation:
            for id_blocco, block in enumerate(text_response.full_text_annotation.pages[0].blocks):
                testo = estrai_testo_da_blocco(block)
                if testo:
                    testi_vision[id_blocco] = testo
                    blocchi_vision[id_blocco] = block
        
        mappatura_testi = []
        
        if testi_vision:
            # 1. Identifica e rimuovi fisicamente i loghi/badge (La prima Chiamata AI)
            analisi_ignorati = identifica_testi_da_ignorare(original_image_bytes, mime_type, testi_vision, logger)
            
            ids_da_ignorare = []
            if isinstance(analisi_ignorati, dict):
                logger.log(f"Ragionamento IA (Filtro Visivo): {analisi_ignorati.get('ragionamento', 'Nessuno')}")
                for i in analisi_ignorati.get("ids_da_ignorare", []):
                    if isinstance(i, (int, str)) and str(i).isdigit():
                        ids_da_ignorare.append(int(i))
                        
            logger.log(f"ID SCARTATI (Cerchi/Loghi/Prodotti) dalla lista: {ids_da_ignorare}")
            
            # Filtra il dizionario inviando a Gemini solo i testi legittimi
            testi_vision_filtrato = {}
            for k, v in testi_vision.items():
                if k not in ids_da_ignorare:
                    testi_vision_filtrato[k] = v
                    
            if not testi_vision_filtrato:
                logger.log("Nessun testo rimasto da tradurre dopo il filtro. Operazione conclusa.")
                mappatura_testi = []
            else:
                
                # Popola le coordinate globali di tutti i blocchi per l'allineamento intelligente
                tutti_i_blocchi_valori = []
                for b_id, block in blocchi_vision.items():
                    xs = []
                    ys = []
                    for p in block.paragraphs:
                        for w in p.words:
                            for v in w.bounding_box.vertices:
                                xs.append(v.x)
                                ys.append(v.y)
                    if xs and ys:
                        tutti_i_blocchi_valori.append({'min_x': min(xs), 'max_x': max(xs), 'min_y': min(ys), 'max_y': max(ys)})

                # 2. Raggruppa e Traduci solo i testi sani (La seconda Chiamata AI)
                classificazione_gemini = analizza_e_traduci_con_gemini(original_image_bytes, mime_type, testi_vision_filtrato, logger)
                filtered_keys = sorted(list(testi_vision_filtrato.keys()))
                
                ids_processati = set() 
                
                for cat in ["banner", "sottotitolo"]:
                    lista_raw = classificazione_gemini.get(cat, [])
                    
                    for item in lista_raw:
                        if not isinstance(item, dict): continue
                        
                        raw_ids = item.get("ids", [])
                        if not raw_ids and "id" in item:
                            raw_ids = item["id"]
                        if not isinstance(raw_ids, list):
                            raw_ids = [raw_ids]
                            
                        valid_ids = []
                        for i in raw_ids:
                            if isinstance(i, (int, str)) and str(i).isdigit():
                                idx = int(i)
                                if idx in testi_vision_filtrato and idx not in ids_processati:
                                    valid_ids.append(idx)
                                    ids_processati.add(idx)
                                    
                        if not valid_ids: continue
                        
                        valid_ids = sorted(list(set(valid_ids)))
                        
                        # LA TUA REGOLA PYTHON D'ACCIAIO SUL BORDO DEI BOX
                        sub_groups = []
                        current_sub = [valid_ids[0]]
                        
                        for i in range(1, len(valid_ids)):
                            prev_id = current_sub[-1]
                            curr_id = valid_ids[i]
                            
                            try:
                                idx_prev = filtered_keys.index(prev_id)
                                idx_curr = filtered_keys.index(curr_id)
                                is_consec = (idx_curr - idx_prev == 1)
                            except ValueError:
                                is_consec = False
                                
                            block_prev = blocchi_vision[prev_id]
                            block_curr = blocchi_vision[curr_id]
                            
                            ys_prev = [v.y for v in block_prev.bounding_box.vertices]
                            ys_curr = [v.y for v in block_curr.bounding_box.vertices]
                            dist_y = min(ys_curr) - max(ys_prev)
                            
                            xs_prev = [v.x for v in block_prev.bounding_box.vertices]
                            xs_curr = [v.x for v in block_curr.bounding_box.vertices]
                            dist_x = min(xs_curr) - max(xs_prev)
                            
                            avg_h = ((max(ys_prev) - min(ys_prev)) + (max(ys_curr) - min(ys_curr))) / 2
                            if avg_h <= 0: avg_h = 10
                            
                            if not is_consec or dist_y > avg_h * 4 or dist_x > avg_h * 15:
                                sub_groups.append(current_sub)
                                current_sub = [curr_id]
                            else:
                                current_sub.append(curr_id)
                                
                        sub_groups.append(current_sub)
                        
                        for sub_group in sub_groups:
                            xs = []
                            ys = []
                            blocchi_da_unire = []
                            testi_originali = []
                            
                            for b_id in sub_group:
                                block = blocchi_vision[b_id]
                                blocchi_da_unire.append(block)
                                testi_originali.append(testi_vision[b_id])
                                
                                for paragraph in block.paragraphs:
                                    for word in paragraph.words:
                                        for v in word.bounding_box.vertices:
                                            xs.append(v.x)
                                            ys.append(v.y)
                                            
                            if not xs or not ys:
                                continue
                                
                            vertici_combinati = [
                                {"x": min(xs), "y": min(ys)}, {"x": max(xs), "y": min(ys)},
                                {"x": max(xs), "y": max(ys)}, {"x": min(xs), "y": max(ys)}
                            ]
                            
                            linee_vertici = estrai_vertici_linee(blocchi_da_unire)
                            if not linee_vertici:
                                linee_vertici = [vertici_combinati]
                            
                            colore_sfondo = estrai_colore_sfondo(img_cv, vertici_combinati)
                            colore_testo = estrai_colore_testo(img_cv, vertici_combinati, colore_sfondo, logger)
                            
                            # Uso del nuovo allineatore che sa guardare anche gli altri box
                            allineamento_originale = rileva_allineamento(blocchi_da_unire, tutti_i_blocchi_valori, img_width)
                            
                            testo_originale_combinato = " ".join(testi_originali).strip()
                            is_bold = item.get("grassetto", False)
                            traduzioni_gemini = item.get("traduzioni", {})
                            is_upper = testo_originale_combinato.isupper() 
                            
                            traduzioni_finali = {}
                            for lang in ["en", "fr", "de", "es", "nl"]:
                                if lang in traduzioni_gemini:
                                    testo_tradotto = traduzioni_gemini[lang]
                                else:
                                    testo_tradotto = testo_originale_combinato 
                                    
                                if isinstance(testo_tradotto, str) and testo_tradotto.strip() != "":
                                    traduzioni_finali[lang] = html.unescape(testo_tradotto)
                                else:
                                    traduzioni_finali[lang] = ""
                            
                            mappatura_testi.append({
                                "ids_originali": sub_group, 
                                "testo_originale": testo_originale_combinato,
                                "testo_tradotto_en": traduzioni_finali["en"],
                                "testo_tradotto_fr": traduzioni_finali["fr"],
                                "testo_tradotto_de": traduzioni_finali["de"],
                                "testo_tradotto_es": traduzioni_finali["es"], 
                                "testo_tradotto_nl": traduzioni_finali["nl"], 
                                "vertici_blocco": vertici_combinati,
                                "linee_vertici": linee_vertici,
                                "colore_sfondo": colore_sfondo,
                                "colore_testo": colore_testo,
                                "grassetto": is_bold,
                                "maiuscolo": is_upper,
                                "tipo": cat,
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
                # Passiamo la larghezza img per supportare l'allineamento
                final_image_bytes = sovrascrivi_testo(original_image_bytes, mappatura_testi, lang, logger, formato_img, img_width)
            else:
                final_image_bytes = original_image_bytes
                
            clean_blob_name = f"{percorso_base_output}/{nome_base}_{lang}{estensione}"
            clean_blob = destination_bucket.blob(clean_blob_name)
            clean_blob.upload_from_string(final_image_bytes, content_type=content_type)

        logger.log("\n=== ELABORAZIONE COMPLETATA CON SUCCESSO ===")

    except Exception as e:
        logger.log(f"\nERRORE CRITICO: {e}")
        raise e
    finally:
        if destination_bucket and nome_base: 
            try:
                testo_log = logger.get_testo_completo()
                percorso_log = f"elaborato_{datetime.now().strftime('%Y-%m-%d')}/{nome_base}_debug.txt"
                log_blob = destination_bucket.blob(percorso_log)
                log_blob.upload_from_string(testo_log, content_type='text/plain')
                print(f"File di log salvato con successo nel bucket come: {percorso_log}")
            except Exception as log_err:
                print(f"Impossibile salvare il file di log nel bucket: {log_err}")

# ==========================================
# --- INIZIO BLOCCO TEST LOCALE ---
# ==========================================
if __name__ == "__main__":
    print("Avvio simulazione test locale multiplo...")
    
    PROJECT_ID = "cloud-platform-northstar-test"
    OUTPUT_BUCKET_NAME = "bkt-for-local-tests-cloud-platform-northstar-test"
    
    os.environ["PROJECT_ID"] = "cloud-platform-northstar-test"
    os.environ["REGION"] = "europe-west1"
    os.environ["OUTPUT_BUCKET_NAME"] = "bkt-for-local-tests-cloud-platform-northstar-test"

    class MockCloudEvent:
        def __init__(self, data):
            self.data = data
            
    nomi_file_da_testare = [
        "esempio_1.png",
        "esempio_2.png",
        "esempio_3.png",
        "esempio_4.png",
        "esempio_5.png",
        "esempio_6.png",
        "esempio_7.png",
        "esempio_8.png",
        "esempio_9.png",
        "esempio_10.png",
        "esempio_11.png",
    ]
    
    for nome_file in nomi_file_da_testare:
        print("\n" + "="*50)
        print(f"🚀 INIZIO TEST SUL FILE: {nome_file}")
        print("="*50)
        
        mock_data = {
            "bucket": "bkt-for-local-tests-cloud-platform-northstar-test", 
            "name": nome_file
        }
        mock_event = MockCloudEvent(mock_data)
        
        try:
            process_infographic_trigger(mock_event)
            print(f"\n✅ Test su {nome_file} completato con successo!")
        except Exception as e:
            print(f"\n❌ Errore durante il test di {nome_file}: {e}")