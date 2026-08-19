import os
import copy
from datetime import datetime
import functions_framework
from google.cloud import storage

# --- IMPORT DEGLI AGENTI ---
from estrai_testo_e_coordinate import estrai_testo_e_coordinate
from agente_filtro import analizza_e_filtra
from agente_traduttore import traduci_testi
from generatore_immagini import genera_infografiche
from agente_reviewer import agente_reviewer 
from agente_corrector import agente_corrector 

# ==========================================
# IMPOSTAZIONI AMBIENTE
# ==========================================
PROJECT_ID = os.environ.get("PROJECT_ID")
OUTPUT_BUCKET_NAME = os.environ.get("OUTPUT_BUCKET_NAME")
REGION = os.environ.get("REGION", "global")

storage_client = storage.Client(project=PROJECT_ID)

def processa_dati_filtro(blocchi_validi):
    testi_md = {}
    m_ruoli = {}
    m_allin = {}
    for i, b_valido in enumerate(blocchi_validi):
        testi_md[i] = b_valido.get("testo_markdown", "")
        m_ruoli[i] = b_valido.get("ruolo", "Sconosciuto")
        m_allin[i] = b_valido.get("allineamento", "sinistra")
    return testi_md, m_ruoli, m_allin

# ==========================================
# CLOUD FUNCTION ENTRY POINT
# ==========================================
@functions_framework.cloud_event
def process_infographic_trigger(cloud_event):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    if file_name.endswith("/"): return
    if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): return

    # Isoliamo il nome base in modo sicuro anche se ci sono sottocartelle
    nome_base_completo = os.path.basename(file_name)
    nome_base, estensione = os.path.splitext(nome_base_completo)

    print(f"=== INIZIO ELABORAZIONE: {nome_base} ===")

    try:
        formato_img = "PNG" if estensione.lower() == ".png" else "JPEG"
        destination_bucket = storage_client.bucket(OUTPUT_BUCKET_NAME)
        source_bucket = storage_client.bucket(bucket_name)
        source_blob = source_bucket.blob(file_name)
        
        # PERCORSO ASSOLUTO SICURO: Nessun cambio di directory necessario
        percorso_immagine = f"/tmp/originale_{nome_base}{estensione}"
        source_blob.download_to_filename(percorso_immagine)
        
        dati_strutturati = estrai_testo_e_coordinate(percorso_immagine)
        risultato_filtro = analizza_e_filtra(percorso_immagine, dati_strutturati)
        blocchi_validi = risultato_filtro.get("blocchi_validi", [])
        testi_md, ruoli, allin = processa_dati_filtro(blocchi_validi)

        if not testi_md:
            print(f"⚠️ [{nome_base}] Nessun testo trovato. Esco.")
            return

        lingue_richieste = ["en", "fr", "de", "es", "nl"]
        risultato_traduzione = traduci_testi(testi_md, ruoli, lingue_richieste)
        traduzioni_base = risultato_traduzione.get("traduzioni", [])
        
        genera_infografiche(
            image_path=percorso_immagine, 
            dati_strutturati=dati_strutturati, 
            blocchi_logici=blocchi_validi, 
            traduzioni=traduzioni_base,
            mappa_allineamenti=allin,
            mappa_ruoli=ruoli,
            nome_base=nome_base
        )
        print(f"🎉 [{nome_base}] RENDERING BASE COMPLETATO!")
        print(f"🔎 [{nome_base}] AVVIO CONTROLLO QUALITÀ (QA)...")
        
        for lang in lingue_richieste:
            img_tradotta_path = f"/tmp/{nome_base}_{lang}.jpg"
            if not os.path.exists(img_tradotta_path): continue
            
            trad_attive_lang = copy.deepcopy(traduzioni_base)
            blocchi_validi_lang = copy.deepcopy(blocchi_validi)
            allin_lang = copy.deepcopy(allin)
            ruoli_lang = copy.deepcopy(ruoli)
            
            offset_attivi_lang = {}
            parole_protette_lang = {}
                
            max_tentativi = 3
            for tentativo in range(1, max_tentativi + 1):
                print(f"--- [{nome_base}] [QA] Lingua: {lang} (Tentativo {tentativo}/{max_tentativi}) ---")
                
                esito_qa = agente_reviewer(percorso_immagine, img_tradotta_path, lang)
                
                if esito_qa.get("status") == "ok":
                    break 
                    
                motivo_ko = esito_qa.get("ragionamento", "Difetto visivo/linguistico generico.")
                
                if tentativo == max_tentativi:
                    print(f"⚠️ [{nome_base}] Limite raggiunto per {lang}. Carico così com'è.")
                    break

                correzione_ia = agente_corrector(percorso_immagine, img_tradotta_path, lang, motivo_ko, trad_attive_lang, dati_strutturati)
                correzioni_lista = correzione_ia.get("correzioni", [])
                
                if not correzioni_lista:
                    break 
                    
                for corr in correzioni_lista:
                    id_logico = corr.get("id_blocco_logico")
                    id_mancante = corr.get("id_ocr_mancante")
                    n_testo = corr.get("nuovo_testo")
                    
                    target_i = -1
                    if id_mancante is not None:
                        target_i = len(blocchi_validi_lang)
                        blocchi_validi_lang.append({"ids_originali": [id_mancante], "ruolo": "Callout", "allineamento": "sinistra"})
                        allin_lang[target_i] = "sinistra"
                        ruoli_lang[target_i] = "Callout"
                    elif id_logico is not None:
                        target_i = id_logico
                        
                    if target_i == -1: continue

                    if n_testo:
                        trovato_trad = False
                        for t in trad_attive_lang:
                            if t.get("id_blocco") == target_i:
                                t["testi_tradotti"][lang] = n_testo
                                trovato_trad = True
                                break
                        if not trovato_trad:
                            trad_attive_lang.append({"id_blocco": target_i, "testi_tradotti": {lang: n_testo}})
                                
                    off_x, off_y = corr.get("offset_x_pct", 0.0), corr.get("offset_y_pct", 0.0)
                    if off_x != 0.0 or off_y != 0.0:
                        offset_attivi_lang[str(target_i)] = {"offset_x_pct": off_x, "offset_y_pct": off_y}

                    p_preservare = corr.get("parole_da_preservare", [])
                    if p_preservare:
                        parole_protette_lang[str(target_i)] = p_preservare

                genera_infografiche(
                    image_path=percorso_immagine, 
                    dati_strutturati=dati_strutturati, 
                    blocchi_logici=blocchi_validi_lang, 
                    traduzioni=[{"id_blocco": t.get("id_blocco"), "testi_tradotti": {lang: t.get("testi_tradotti", {}).get(lang, "")}} for t in trad_attive_lang],
                    mappa_allineamenti=allin_lang,
                    mappa_ruoli=ruoli_lang,
                    offset_correttivi=offset_attivi_lang,
                    parole_da_preservare=parole_protette_lang,
                    nome_base=nome_base
                )

        print(f"=== [{nome_base}] AVVIO CARICAMENTO SU BUCKET ===")
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        percorso_base_output = f"elaborato_{current_date_str}"
        content_type = f'image/{formato_img.lower()}'

        # SALVATAGGIO SOLO DELLE IMMAGINI TRADOTTE
        for lang in lingue_richieste:
            img_tradotta_path = f"/tmp/{nome_base}_{lang}.jpg"
            if os.path.exists(img_tradotta_path):
                clean_blob_name = f"{percorso_base_output}/{nome_base}_{lang}{estensione}"
                clean_blob = destination_bucket.blob(clean_blob_name)
                clean_blob.upload_from_filename(img_tradotta_path, content_type=content_type)
                print(f"✅ [{nome_base}] Upload completato: {clean_blob_name}")

        print(f"🚀 [{nome_base}] PIPELINE COMPLETATA CON SUCCESSO!")

    except Exception as e:
        print(f"❌ [{nome_base}] ERRORE CRITICO: {e}")
        raise e