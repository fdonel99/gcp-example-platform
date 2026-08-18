import os
from PIL import Image, ImageDraw, ImageFont

def calcola_sfondo(img, min_x, min_y, max_x, max_y):
    pad = 5; punti = []; w, h = img.size
    for x in range(max(0, min_x), min(w, max_x), max(1, (max_x - min_x)//10)):
        if min_y - pad > 0: punti.append(img.getpixel((x, min_y - pad)))
        if max_y + pad < h: punti.append(img.getpixel((x, max_y + pad)))
    for y in range(max(0, min_y), min(h, max_y), max(1, (max_y - min_y)//10)):
        if min_x - pad > 0: punti.append(img.getpixel((min_x - pad, y)))
        if max_x + pad < w: punti.append(img.getpixel((max_x + pad, y)))
        
    if not punti: return (255, 255, 255)
    r = sorted([p[0] for p in punti])[len(punti)//2]
    g = sorted([p[1] for p in punti])[len(punti)//2]
    b = sorted([p[2] for p in punti])[len(punti)//2]
    return (r, g, b)

def disegna_testo_markdown(draw, testo_md, path_reg, path_bold, box_x, box_y, box_width, box_height, color, allineamento="sinistra", ruolo="Sconosciuto"):
    min_size = 12
    max_size = 120
    
    # --- 1. PARSING DEL MARKDOWN OTTIMIZZATO ---
    # Analizziamo il testo in paragrafi UNA sola volta. 
    # Questo mantiene attiva la memoria del grassetto tra una riga e l'altra!
    paragrafi = testo_md.split('\n')
    struttura_paragrafi = []
    
    bold_mode_global = False  # La memoria del grassetto ora è GLOBALE
    
    for paragrafo in paragrafi:
        raw_words = paragrafo.split()
        if not raw_words:
            struttura_paragrafi.append([]) # Preserva le righe vuote (doppio a capo)
            continue
            
        # Gestione punteggiatura attaccata
        words = []
        for rw in raw_words:
            if rw.replace('**', '') in [':', ';', '!', '?', '-', '»', '”'] and words:
                words[-1] = words[-1] + " " + rw
            else:
                words.append(rw)

        words_info = []
        for w in words:
            clean_w = w
            
            # Caso 1: Parola interamente avvolta in **parola**
            if clean_w.startswith('**') and clean_w.endswith('**') and len(clean_w) >= 4:
                words_info.append({"text": clean_w[2:-2], "bold": True})
                continue
                
            # Caso 2: Inizio del grassetto
            if clean_w.startswith('**'):
                bold_mode_global = True
                clean_w = clean_w[2:]
                
            # Caso 3: Fine del grassetto
            end_bold = False
            if '**' in clean_w:
                end_bold = True
                clean_w = clean_w.replace('**', '')
                
            words_info.append({"text": clean_w, "bold": bold_mode_global})
            
            if end_bold: 
                bold_mode_global = False
                
        struttura_paragrafi.append(words_info)

    # --- 2. CALCOLO DELLA DIMENSIONE E IMPAGINAZIONE ---
    moltiplicatore_altezza = 1.35 if ruolo == "Titolo" else 1.15
    larghezza_utile = box_width
    
    best_lines = []
    best_total_h = 0
    best_line_h = 0
        
    for size in range(max_size, min_size - 1, -2):
        if size > box_height * 0.90 and ruolo != "Titolo":
            continue
            
        f_reg = ImageFont.truetype(path_reg, size)
        f_bold = ImageFont.truetype(path_bold, size)
        
        lines = []
        word_overflow = False
        
        for paragrafo_words in struttura_paragrafi:
            if not paragrafo_words:
                lines.append({"words": [], "w": 0})
                continue
                
            current_line = []
            current_w = 0
            
            for w_info in paragrafo_words:
                f_active = f_bold if w_info["bold"] else f_reg
                w_text = w_info["text"]
                w_width = f_active.getlength(w_text)
                w_width_with_space = f_active.getlength(w_text + " ")
                
                if w_width > larghezza_utile:
                    word_overflow = True
                    break
                    
                if current_w + w_width > larghezza_utile and current_line:
                    line_w_exact = current_w - current_line[-1]["w_space"] + current_line[-1]["w"]
                    lines.append({"words": current_line, "w": line_w_exact})
                    current_line = []
                    current_w = 0
                    
                current_line.append({"text": w_text, "f": f_active, "w": w_width, "w_space": w_width_with_space})
                current_w += w_width_with_space
                
            if word_overflow: break
                
            if current_line:
                line_w_exact = current_w - current_line[-1]["w_space"] + current_line[-1]["w"]
                lines.append({"words": current_line, "w": line_w_exact})
                
        if word_overflow: continue
            
        line_height = size * 1.15
        total_h = len(lines) * line_height
        
        if total_h <= box_height * moltiplicatore_altezza:
            best_lines = lines; best_total_h = total_h; best_line_h = line_height
            break
            
    if not best_lines:
        best_lines = lines; best_total_h = total_h; best_line_h = line_height
        
    current_y = box_y + (box_height - best_total_h) / 2
    
    for line in best_lines:
        if not line["words"]: 
            current_y += best_line_h
            continue
        
        inizio_x = box_x
        
        if allineamento == "centro":
            current_x = inizio_x + (larghezza_utile - line["w"]) / 2
        elif allineamento == "destra":
            current_x = inizio_x + (larghezza_utile - line["w"])
        else:
            current_x = inizio_x 
        
        for w in line["words"]:
            draw.text((current_x, current_y), w["text"], font=w["f"], fill=color)
            current_x += w["w_space"]
            
        current_y += best_line_h

def genera_infografiche(image_path, dati_strutturati, blocchi_logici, traduzioni, mappa_allineamenti, mappa_ruoli, offset_correttivi=None, parole_da_preservare=None):
    print("\n🎨 Avvio motore di rendering (Geometria Intelligente con Scudo)...")
    if offset_correttivi is None: offset_correttivi = {}
    if parole_da_preservare is None: parole_da_preservare = {}
        
    dir_corrente = os.path.dirname(os.path.abspath(__file__))
    FONT_REG = os.path.join(dir_corrente, "montserrat.ttf")
    FONT_BOLD = os.path.join(dir_corrente, "montserrat-bold.ttf")
    
    lingue = set()
    for trad in traduzioni:
        for lang in trad.get("testi_tradotti", {}).keys():
            lingue.add(lang)
            
    mappa_traduzioni = {lang: {} for lang in lingue}
    for trad in traduzioni:
        id_gruppo = trad.get("id_blocco")
        for lang, text in trad.get("testi_tradotti", {}).items():
            mappa_traduzioni[lang][id_gruppo] = text

    for lang in lingue:
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        for i, blocco_logico in enumerate(blocchi_logici):
            testo_tradotto_md = mappa_traduzioni[lang].get(i, "")
            if not testo_tradotto_md: continue

            ids_originali = blocco_logico.get("ids_originali", [])
            if not ids_originali:
                ids_originali = [blocco_logico.get("id_blocco")]
                
            idx_str = str(i)
            parole_salve = parole_da_preservare.get(idx_str, [])
            parole_salve_lower = [ps.lower() for ps in parole_salve]

            tutti_x = []
            tutti_y = []
            colore_testo = (0,0,0)
            trovato_colore = False

            # --- MAGIA MATEMATICA: CALCOLO DELLE COORDINATE ESCLUDENDO LO SCUDO ---
            for id_orig in ids_originali:
                blocco_ocr = next((b for b in dati_strutturati if b["id_blocco"] == id_orig), None)
                if blocco_ocr:
                    for p in blocco_ocr["parole"]:
                        # Se la parola è nello scudo, NON usare le sue coordinate per il calcolo!
                        if p["testo"].lower() in parole_salve_lower:
                            continue
                            
                        # Troviamo il colore solo dalle parole non protette
                        if not trovato_colore:
                            rgb = p.get("colore_rgb", {"r":0, "g":0, "b":0})
                            colore_testo = (rgb["r"], rgb["g"], rgb["b"])
                            trovato_colore = True
                            
                        for v in p["vertici"]:
                            tutti_x.append(v["x"])
                            tutti_y.append(v["y"])
                            
            # Se tutte le parole del blocco erano protette, non c'è nulla da stampare
            if not tutti_x: continue

            # Ora min_x è il punto esatto in cui iniziava il testo originale da sostituire!
            min_x, max_x = min(tutti_x), max(tutti_x)
            min_y, max_y = min(tutti_y), max(tutti_y)
            box_width, box_height = max_x - min_x, max_y - min_y
            
            # Calcoliamo lo sfondo attorno alle sole parole da cancellare
            colore_sfondo = calcola_sfondo(img, min_x, min_y, max_x, max_y)
            
            # --- FASE 1: CANCELLAZIONE DI PRECISIONE ---
            for id_orig in ids_originali:
                blocco_ocr = next((b for b in dati_strutturati if b["id_blocco"] == id_orig), None)
                if blocco_ocr:
                    for p in blocco_ocr["parole"]:
                        # Non cancelliamo le parole scudate
                        if p["testo"].lower() in parole_salve_lower:
                            continue
                            
                        pxs = [v["x"] for v in p["vertici"]]
                        pys = [v["y"] for v in p["vertici"]]
                        if pxs and pys:
                            draw.rectangle([min(pxs), min(pys)-2, max(pxs)+2, max(pys)+2], fill=colore_sfondo)

            allin = mappa_allineamenti.get(i, "sinistra")
            ruolo_calc = mappa_ruoli.get(i, "Sconosciuto")

            # --- FASE 2: OFFSET DELL'IA SULLE NUOVE COORDINATE ---
            if idx_str in offset_correttivi:
                off_x_pct = offset_correttivi[idx_str].get("offset_x_pct", 0.0)
                off_y_pct = offset_correttivi[idx_str].get("offset_y_pct", 0.0)
                
                pixel_spostamento_x = int(img.width * off_x_pct)
                pixel_spostamento_y = int(img.height * off_y_pct)
                
                min_x += pixel_spostamento_x
                min_y += pixel_spostamento_y
                
                if pixel_spostamento_x > 0:
                    box_width -= pixel_spostamento_x 
            
            disegna_testo_markdown(
                draw=draw, 
                testo_md=testo_tradotto_md, 
                path_reg=FONT_REG, 
                path_bold=FONT_BOLD, 
                box_x=min_x, 
                box_y=min_y, 
                box_width=box_width, 
                box_height=box_height, 
                color=colore_testo,
                allineamento=allin,
                ruolo=ruolo_calc
            )
            
        nome_file = f"infografica_{lang}.jpg"
        img.save(nome_file, quality=95)
        print(f"✅ Salvata: {nome_file}")