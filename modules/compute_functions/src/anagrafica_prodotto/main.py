import datetime
import os
import pandas as pd
from google.cloud import bigquery
import google.auth
import gspread
from gspread_dataframe import set_with_dataframe
import functions_framework

@functions_framework.http
def anagrafica_prodotto(request):
    # 1. Lettura del project_id per determinare l'ambiente
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', '')
    
    if not project_id:
        return "Errore: GOOGLE_CLOUD_PROJECT non configurato.", 500

    dataset_table = 'NORTHSTAR.ANAGRAFICA_PRODOTTO'
    
    # 2. Impostazione dell'ID del Google Sheet in base all'ambiente
    if 'test' in project_id.lower():
        sheet_id = '1EKLLgHBo3zIdbgMOhThjR54J15UngDdRXix79FOP5DY'
        print(f"Ambiente di TEST rilevato. Uso Sheet ID: {sheet_id}")
    else:
        sheet_id = '16a2zUbm-dVfHHxLIa9F0uE-VNDUQNQplxr5_i_S69ps'
        print(f"Ambiente di PROD rilevato. Uso Sheet ID: {sheet_id}")
    
    # Nome del foglio per l'esecuzione odierna
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    sheet_name = f'ANAGRAFICA_{today_str}'

    # === LA TUA QUERY SQL COMPLETA INVARIATA ===
    sql_create_table = f"""
        -- 1. Funzione di decodifica HTML
        CREATE TEMP FUNCTION HTML_DECODE(testo STRING) 
        RETURNS STRING 
        LANGUAGE js AS r'''
          if (testo == null) return null;
          var entities = {{
              "&quot;": "'", "&#34;": "'", "&#39;": "'", "&apos;": "'",
              "&amp;": "&", "&#38;": "&", "&lt;": "<", "&#60;": "<", "&gt;": ">", "&#62;": ">",
              "&agrave;": "à", "&egrave;": "è", "&eacute;": "é", "&igrave;": "ì", "&ograve;": "ò", "&ugrave;": "ù",
              "&Agrave;": "À", "&Egrave;": "È", "&Eacute;": "É", "&Igrave;": "Ì", "&Ograve;": "Ò", "&Ugrave;": "Ù",
              "&nbsp;": " ", "&#160;": " ", "&euro;": "€", "&#8364;": "€", "&copy;": "©", "&reg;": "®",
              "&ndash;": "-", "&#8211;": "-"
          }};
          return testo.replace(/&[#A-Za-z0-9]+;/g, function(match) {{
              return entities[match] || match; 
          }});
        ''';

        -- 2. Creazione della tabella
        CREATE OR REPLACE TABLE `{project_id}.{dataset_table}` AS (
            WITH additional_attributes AS (
                SELECT RTRIM(sku) AS sku,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'fornitore=%' THEN SUBSTR(additional_attributes, 11) END) AS fornitore,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'ean=%' THEN SUBSTR(additional_attributes, 5) END) AS ean,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'pdf=%' THEN SUBSTR(additional_attributes, 5) END) AS pdf,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'genere=%' THEN SUBSTR(additional_attributes, 8) END) AS genere,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'marca=%' THEN SUBSTR(additional_attributes, 7) END) AS marca,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'costo=%' THEN SUBSTR(additional_attributes, 7) END) AS costo,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'dimensioni=%' THEN SUBSTR(additional_attributes, 12) END) AS dimensioni,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'dettagli=%' THEN SUBSTR(additional_attributes, 10) END) AS dettagli,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'manufacturer=%' THEN SUBSTR(additional_attributes, 14) END) AS manufacturer,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'tp_ds=%' THEN SUBSTR(additional_attributes, 7) END) AS tp_ds,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'diametro_ruote=%' THEN SUBSTR(additional_attributes, 16) END) AS diametro_ruote,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'ebay_it=%' THEN SUBSTR(additional_attributes, 9) END) AS ebay_it,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'personaggio=%' THEN SUBSTR(additional_attributes, 13) END) AS personaggio,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_it=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_it,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_fr=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_fr,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_de=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_de,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_gb=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_gb,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_es=%' THEN SUBSTR(additional_attributes, 17) END) AS amazon_price_es,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_it_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_it_sconto,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_fr_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_fr_sconto,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_gb_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_gb_sconto,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_de_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_de_sconto,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_price_es_sconto=%' THEN SUBSTR(additional_attributes, 24) END) AS amazon_price_es_sconto,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_it_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_it_special_to_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_fr_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_fr_special_to_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_de_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_de_special_to_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_es_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_es_special_to_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'amazon_gb_special_to_date=%' THEN SUBSTR(additional_attributes, 27) END) AS amazon_gb_special_to_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'special_to_date=%' THEN SUBSTR(additional_attributes, 17) END) AS special_to_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'special_from_date=%' THEN SUBSTR(additional_attributes, 19) END) AS special_from_date,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'tax_class_name=%' THEN SUBSTR(additional_attributes, 16) END) AS iva,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'privalia_mktplace=%' THEN SUBSTR(additional_attributes, 19) END) AS privalia_mktplace,
                MAX(CASE WHEN LOWER(additional_attributes) LIKE 'privalia_mktplace_raccomanded=%' THEN SUBSTR(additional_attributes, 31) END) AS privalia_mktplace_raccomanded
                FROM `{project_id}.NORTHSTAR.dbo_m2_additional_attributes`
                GROUP BY RTRIM(sku)),

            gallery AS (
                SELECT sku,
                image_array[SAFE_OFFSET(0)] AS gallery_0, image_array[SAFE_OFFSET(1)] AS gallery_1, image_array[SAFE_OFFSET(2)] AS gallery_2, image_array[SAFE_OFFSET(3)] AS gallery_3, image_array[SAFE_OFFSET(4)] AS gallery_4, image_array[SAFE_OFFSET(5)] AS gallery_5, image_array[SAFE_OFFSET(6)] AS gallery_6, image_array[SAFE_OFFSET(7)] AS gallery_7, image_array[SAFE_OFFSET(8)] AS gallery_8, image_array[SAFE_OFFSET(9)] AS gallery_9
                FROM (
                    SELECT RTRIM(sku) AS sku, SPLIT(REPLACE(additional_images, '[path]', ''), ',') AS image_array
                    FROM `{project_id}.NORTHSTAR.dbo_m2_articoli`
                )
            ),

            base_data AS (
                SELECT COALESCE(a.sku, RTRIM(b.sku)) AS sku, a.* EXCEPT(sku),
                b.name, b.product_type, b.categories, b.color, b.size, b.price, b.special_price, b.qty, b.description, b.short_description, b.parent,
                LTRIM(REPLACE(b.thumbnail_image, '[path]', ''), '/') AS thumbnail_image, LTRIM(REPLACE(b.base_image, '[path]', ''), '/') AS base_image, LTRIM(REPLACE(b.small_image, '[path]', ''), '/') AS small_image,
                LTRIM(ga.gallery_0, '/') AS gallery_0, LTRIM(ga.gallery_1, '/') AS gallery_1, LTRIM(ga.gallery_2, '/') AS gallery_2, LTRIM(ga.gallery_3, '/') AS gallery_3, LTRIM(ga.gallery_4, '/') AS gallery_4, LTRIM(ga.gallery_5, '/') AS gallery_5, LTRIM(ga.gallery_6, '/') AS gallery_6, LTRIM(ga.gallery_7, '/') AS gallery_7, LTRIM(ga.gallery_8, '/') AS gallery_8, LTRIM(ga.gallery_9, '/') AS gallery_9
                FROM additional_attributes a 
                FULL OUTER JOIN `{project_id}.NORTHSTAR.dbo_m2_articoli` b ON a.sku = RTRIM(b.sku)
                FULL OUTER JOIN gallery ga ON a.sku = ga.sku
            )

            SELECT sku,
                * EXCEPT(sku, thumbnail_image, base_image, small_image, gallery_0, gallery_1, gallery_2, gallery_3, gallery_4, gallery_5, gallery_6, gallery_7, gallery_8, gallery_9, name, description, short_description, dettagli, costo, amazon_price_it, amazon_price_fr, amazon_price_de, amazon_price_gb, amazon_price_es, amazon_price_it_sconto, amazon_price_fr_sconto, amazon_price_gb_sconto, amazon_price_de_sconto, amazon_price_es_sconto),
                HTML_DECODE(name) AS name, HTML_DECODE(description) AS description, HTML_DECODE(short_description) AS short_description, HTML_DECODE(dettagli) AS dettagli,
                REPLACE(costo, '.', ',') AS costo, REPLACE(amazon_price_it, '.', ',') AS amazon_price_it, REPLACE(amazon_price_fr, '.', ',') AS amazon_price_fr, REPLACE(amazon_price_de, '.', ',') AS amazon_price_de, REPLACE(amazon_price_gb, '.', ',') AS amazon_price_gb, REPLACE(amazon_price_es, '.', ',') AS amazon_price_es, REPLACE(amazon_price_it_sconto, '.', ',') AS amazon_price_it_sconto, REPLACE(amazon_price_fr_sconto, '.', ',') AS amazon_price_fr_sconto, REPLACE(amazon_price_gb_sconto, '.', ',') AS amazon_price_gb_sconto, REPLACE(amazon_price_de_sconto, '.', ',') AS amazon_price_de_sconto, REPLACE(amazon_price_es_sconto, '.', ',') AS amazon_price_es_sconto,
                CASE WHEN NULLIF(base_image, '') IS NOT NULL AND LENGTH(base_image) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(base_image, 1, 2), '/', base_image) ELSE base_image END AS base_image,
                CASE WHEN NULLIF(thumbnail_image, '') IS NOT NULL AND LENGTH(COALESCE(base_image, thumbnail_image)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, thumbnail_image), 1, 2), '/', thumbnail_image) ELSE thumbnail_image END AS thumbnail_image,
                CASE WHEN NULLIF(small_image, '') IS NOT NULL AND LENGTH(COALESCE(base_image, small_image)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, small_image), 1, 2), '/', small_image) ELSE small_image END AS small_image,
                CASE WHEN NULLIF(gallery_0, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_0)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_0), 1, 2), '/', gallery_0) ELSE gallery_0 END AS gallery_0,
                CASE WHEN NULLIF(gallery_1, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_1)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_1), 1, 2), '/', gallery_1) ELSE gallery_1 END AS gallery_1,
                CASE WHEN NULLIF(gallery_2, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_2)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_2), 1, 2), '/', gallery_2) ELSE gallery_2 END AS gallery_2,
                CASE WHEN NULLIF(gallery_3, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_3)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_3), 1, 2), '/', gallery_3) ELSE gallery_3 END AS gallery_3,
                CASE WHEN NULLIF(gallery_4, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_4)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_4), 1, 2), '/', gallery_4) ELSE gallery_4 END AS gallery_4,
                CASE WHEN NULLIF(gallery_5, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_5)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_5), 1, 2), '/', gallery_5) ELSE gallery_5 END AS gallery_5,
                CASE WHEN NULLIF(gallery_6, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_6)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_6), 1, 2), '/', gallery_6) ELSE gallery_6 END AS gallery_6,
                CASE WHEN NULLIF(gallery_7, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_7)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_7), 1, 2), '/', gallery_7) ELSE gallery_7 END AS gallery_7,
                CASE WHEN NULLIF(gallery_8, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_8)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_8), 1, 2), '/', gallery_8) ELSE gallery_8 END AS gallery_8,
                CASE WHEN NULLIF(gallery_9, '') IS NOT NULL AND LENGTH(COALESCE(base_image, gallery_9)) >= 2 THEN CONCAT('https://marketplace.toctocshop.com/media/sincro/img/', SUBSTR(COALESCE(base_image, gallery_9), 1, 2), '/', gallery_9) ELSE gallery_9 END AS gallery_9
            FROM base_data
        );
    """

    try:
        # FASE 1: Ricrea la tabella aggiornata su BigQuery
        bq_client = bigquery.Client(project=project_id)
        print("1. Ricreazione tabella su BigQuery in corso...")
        bq_client.query(sql_create_table).result()
        print("Tabella creata con successo.")

        # FASE 2: Estrae i dati
        print("2. Scaricamento dati nel dataframe...")
        query_select = f"SELECT * FROM `{project_id}.{dataset_table}`"
        df = bq_client.query(query_select).to_dataframe()

        print("Pulizia dei caratteri di controllo e formattazione NaN...")
        # Pulizia caratteri non supportati
        df = df.replace(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', regex=True)

        # FASE 3: Autenticazione e connessione a Google Sheets
        print(f"3. Connessione a Google Sheets (ID: {sheet_id})...")
        credentials, _ = google.auth.default(scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(sheet_id)

        # FASE 4: Gestione del foglio per i dati di oggi
        print(f"4. Creazione del nuovo foglio: '{sheet_name}'...")
        
        # Recupera tutti i fogli esistenti
        tutti_i_fogli = sh.worksheets()
        worksheet_oggi = None
        
        # Cerca se il foglio esiste già, ignorando maiuscole e minuscole!
        for ws in tutti_i_fogli:
            if ws.title.lower() == sheet_name.lower():
                worksheet_oggi = ws
                break
                
        if worksheet_oggi:
            print(f"Il foglio '{worksheet_oggi.title}' esiste già. Lo svuoto per sovrascriverlo...")
            worksheet_oggi.clear()
        else:
            print("Il foglio non esiste. Lo creo in posizione 0...")
            # Crea il foglio in posizione 0 (il primo a sinistra)
            worksheet_oggi = sh.add_worksheet(title=sheet_name, rows=len(df)+1, cols=len(df.columns), index=0)

        print("Scrittura dati in corso...")
        # Usa set_with_dataframe (molto più veloce del caricamento riga per riga)
        set_with_dataframe(worksheet_oggi, df, include_index=False, include_column_header=True)
        print("Scrittura completata.")

        # --- NUOVA SEZIONE: Aggiornamento automatico del filtro ---
        print("Aggiornamento del filtro di Google Sheets...")
        try:
            # 1. Rimuove eventuali filtri rimasti incastrati dalle esecuzioni precedenti
            worksheet_oggi.clear_basic_filter()
        except Exception:
            pass # Se non c'era nessun filtro, ignora l'errore e va avanti
            
        # 2. Applica un nuovo filtro pulito che copre automaticamente tutti i dati appena caricati
        worksheet_oggi.set_basic_filter()
        # ----------------------------------------------------------

        # FASE 5: Pulizia dei fogli vecchi (massimo 10 fogli)
        print("5. Controllo storico fogli (Max 10 consentiti)...")

        fogli_predefiniti = ["Foglio1", "Sheet1"]
        for nome_predefinito in fogli_predefiniti:
            try:
                foglio_vuoto = sh.worksheet(nome_predefinito)
                # Verifica che non sia l'unico foglio rimasto prima di eliminarlo
                if len(sh.worksheets()) > 1:
                    sh.del_worksheet(foglio_vuoto)
                    print(f"Foglio di default '{nome_predefinito}' eliminato con successo.")
            except gspread.exceptions.WorksheetNotFound:
                pass

        tutti_i_fogli = sh.worksheets()
        
        # Se abbiamo più di 10 fogli
        if len(tutti_i_fogli) > 10:
            # I fogli sono ordinati da sinistra a destra, quindi i più vecchi sono in fondo alla lista
            fogli_da_eliminare = tutti_i_fogli[10:]
            for foglio in fogli_da_eliminare:
                print(f"Eliminazione del foglio vecchio: '{foglio.title}'...")
                sh.del_worksheet(foglio)
        else:
            print(f"Fogli attuali: {len(tutti_i_fogli)}. Nessuna pulizia necessaria.")

        messaggio = f"Successo! Dati caricati nel foglio '{sheet_name}' e storico ottimizzato."
        print(messaggio)
        return (messaggio, 200)

    except Exception as e:
        errore = f"Si è verificato un errore: {str(e)}"
        print(errore)
        return (errore, 500)