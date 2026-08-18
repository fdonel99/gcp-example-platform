import os
import cv2
import numpy as np
from google.cloud import documentai
from google.api_core.client_options import ClientOptions

PROJECT_ID = "cloud-platform-northstar-test"
LOCATION = "eu"
PROCESSOR_ID = "681f64e11b506d63"

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
        return (255, 255, 255)

def estrai_colore_testo(img_cv, vertici, colore_sfondo):
    try:
        xs = [v['x'] for v in vertici]
        ys = [v['y'] for v in vertici]
        min_x, max_x = max(0, min(xs)), max(xs)
        min_y, max_y = max(0, min(ys)), max(ys)
        
        crop = img_cv[min_y:max_y, min_x:max_x]
        if crop.size == 0: return {"r": 50, "g": 50, "b": 50}
            
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
                
        return {"r": int(best_color[2]), "g": int(best_color[1]), "b": int(best_color[0])}
    except Exception:
        return {"r": 50, "g": 50, "b": 50}

def estrai_testo_da_segmento(text_anchor, testo_completo):
    testo = ""
    for segment in text_anchor.text_segments:
        start = segment.start_index if segment.start_index else 0
        end = segment.end_index
        testo += testo_completo[start:end]
    return testo.strip()

def estrai_testo_e_coordinate(file_path):
    print(f"🔄 Avvio estrazione Document AI + OpenCV per: {os.path.basename(file_path)}")
    
    endpoint_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=endpoint_options)
    name = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

    with open(file_path, "rb") as image_file:
        image_content = image_file.read()

    nparr = np.frombuffer(image_content, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    raw_document = documentai.RawDocument(content=image_content, mime_type="image/jpeg")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)

    result = client.process_document(request=request)
    document = result.document
    testo_completo = document.text
    
    risultato_json = []

    for pagina in document.pages:
        img_width = pagina.dimension.width
        img_height = pagina.dimension.height
        tutti_i_tokens = pagina.tokens
        
        for id_blocco, blocco in enumerate(pagina.blocks):
            blocco_dati = {"id_blocco": id_blocco, "parole": []}
            
            if not blocco.layout.text_anchor.text_segments: continue
            block_start = blocco.layout.text_anchor.text_segments[0].start_index if blocco.layout.text_anchor.text_segments[0].start_index else 0
            block_end = blocco.layout.text_anchor.text_segments[-1].end_index
            
            for token in tutti_i_tokens:
                if not token.layout.text_anchor.text_segments: continue
                    
                t_start = token.layout.text_anchor.text_segments[0].start_index if token.layout.text_anchor.text_segments[0].start_index else 0
                t_end = token.layout.text_anchor.text_segments[-1].end_index
                
                if t_start >= block_start and t_end <= block_end:
                    testo_parola = estrai_testo_da_segmento(token.layout.text_anchor, testo_completo)
                    if not testo_parola: continue

                    is_bold = token.style_info.bold if token.style_info else False
                        
                    vertici = []
                    if token.layout.bounding_poly.normalized_vertices:
                        for v in token.layout.bounding_poly.normalized_vertices:
                            vertici.append({"x": int(v.x * img_width), "y": int(v.y * img_height)})
                    
                    colore_sfondo_rgb = estrai_colore_sfondo(img_cv, vertici)
                    colore_testo_reale = estrai_colore_testo(img_cv, vertici, colore_sfondo_rgb)

                    blocco_dati["parole"].append({
                        "testo": testo_parola,
                        "bold": is_bold,
                        "colore_rgb": colore_testo_reale,
                        "vertici": vertici
                    })
            
            if blocco_dati["parole"]:
                risultato_json.append(blocco_dati)

    return risultato_json