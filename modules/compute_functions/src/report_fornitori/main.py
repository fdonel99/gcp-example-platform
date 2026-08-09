import datetime
import os
import pandas as pd
from google.cloud import bigquery
import google.auth
import gspread
from gspread_dataframe import set_with_dataframe
import functions_framework

@functions_framework.http
def report_fornitori(request):
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', '')
    
    if not project_id:
        return "Errore: GOOGLE_CLOUD_PROJECT non configurato.", 500

    dataset_table = 'NORTHSTAR.REPORT_FORNITORI'
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    if 'test' in project_id.lower():
        sheet_id = '1Cf6rwBtMeKp5acTnb62X6r9WAPJeUnK5yKVLoh18LJQ'
        print(f"Ambiente di TEST rilevato. Uso Sheet ID: {sheet_id}")
        sheet_name = f'REPORT_FORNITORI_TEST_{today_str}'
    else:
        sheet_id = '1o0nppIt-GPVMyXg48XmTBC8wU3sapJFdZH7Wpj4fZ84'
        print(f"Ambiente di PROD rilevato. Uso Sheet ID: {sheet_id}")
        sheet_name = f'REPORT_FORNITORI_{today_str}'

    sql_create_table = f"""
        CREATE OR REPLACE TABLE `{project_id}.{dataset_table}` AS ( 
          SELECT 
            sku, 
            fornitore, 
            SAFE_CAST(REPLACE(costo, ',', '.') AS FLOAT64) AS costo,
            iva, 
            nazione_des,
            pagamento_def,
            TRIM(name, '"') AS nome,
            SAFE.PARSE_DATE('%Y%m%d', SUBSTR(DATAISO, 1, 8)) AS data_spedizione,
            SUBSTR(DATAISO, 1, 4) AS anno_spedizione,
            SUBSTR(DATAISO, 5, 2) AS mese_spedizione,
            SUM(SAFE_CAST(REPLACE(prezzo_totale, ',', '.') AS FLOAT64)) AS prezzo_totale,
            SUM(qta_spedita) AS tot_qta_spedita,
            SAFE_DIVIDE(SUM(SAFE_CAST(REPLACE(prezzo_totale, ',', '.') AS FLOAT64)), SUM(qta_spedita)) AS prezzo_unitario,
            SUM(CASE WHEN SAFE_CAST(REPLACE(PREZZO_UNITARIO , "," , ".") AS FLOAT64) = 0 THEN qta_spedita ELSE 0 END) AS qta_gratuita
          FROM (
            SELECT 
              o.sku, 
              p.name, 
              p.fornitore, 
              p.costo,
              o.qta_spedita, 
              o.ordine, 
              o.DATAISO, 
              t.newnew as pagamento_def, 
              o.PREZZO_UNITARIO, 
              o.PREZZO_TOTALE,
              p.iva AS iva,
              t.NAZIONE_DES
            FROM `{project_id}.NORTHSTAR.dbo_ordini_righe` o 
            LEFT JOIN `{project_id}.NORTHSTAR.ANAGRAFICA_PRODOTTO` p USING(sku)
            LEFT JOIN `{project_id}.NORTHSTAR.dbo_ordini_testate_pag` t USING(ORDINE)
            WHERE o.DATA_SPEDIZIONE != "000000"
          )
          GROUP BY ALL
        );
    """

    try:
        bq_client = bigquery.Client(project=project_id)
        print("1. Ricreazione tabella su BigQuery in corso...")
        bq_client.query(sql_create_table).result()
        print("Tabella creata con successo.")

        print("2. Scaricamento dati aggregati nel dataframe...")

        query_select = f"""
            SELECT 
                sku, 
                fornitore, 
                costo, 
                iva, 
                nazione_des, 
                pagamento_def, 
                nome, 
                anno_spedizione, 
                mese_spedizione,
                SUM(prezzo_totale) AS prezzo_totale,
                SUM(tot_qta_spedita) AS tot_qta_spedita,
                SAFE_DIVIDE(SUM(prezzo_totale), SUM(tot_qta_spedita)) AS prezzo_unitario,
                SUM(qta_gratuita) AS qta_gratuita
            FROM `{project_id}.{dataset_table}`
            GROUP BY ALL
        """
        
        df = bq_client.query(query_select).to_dataframe()

        print(f"DEBUG: DataFrame shape: {df.shape}")
        if df.empty:
            print("ATTENZIONE: Il DataFrame è vuoto! La query BigQuery non ha restituito righe.")
        else:
            print("Pulizia dei caratteri di controllo non supportati...")
            df = df.replace(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', regex=True)

        print(f"3. Connessione a Google Sheets (ID: {sheet_id})...")
        credentials, _ = google.auth.default(scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(sheet_id)

        print(f"4. Creazione del nuovo foglio: '{sheet_name}'...")
        
        tutti_i_fogli = sh.worksheets()
        worksheet_oggi = None
        
        for ws in tutti_i_fogli:
            if ws.title.lower() == sheet_name.lower():
                worksheet_oggi = ws
                break
                
        if worksheet_oggi:
            print(f"Il foglio '{worksheet_oggi.title}' esiste già. Lo svuoto per sovrascriverlo...")
            worksheet_oggi.clear()
        else:
            print("Il foglio non esiste. Lo creo in posizione 0...")
            worksheet_oggi = sh.add_worksheet(title=sheet_name, rows=len(df)+1, cols=len(df.columns), index=0)

        print("Scrittura dati in corso...")
        set_with_dataframe(worksheet_oggi, df, include_index=False, include_column_header=True)
        print("Scrittura completata.")
        
        print("Aggiornamento del filtro di Google Sheets...")
        try:
            worksheet_oggi.clear_basic_filter()
        except Exception:
            pass 

        worksheet_oggi.set_basic_filter()

        print("5. Controllo e pulizia fogli...")
        
        fogli_predefiniti = ["Foglio1", "Sheet1"]
        for nome_predefinito in fogli_predefiniti:
            try:
                foglio_vuoto = sh.worksheet(nome_predefinito)
                if len(sh.worksheets()) > 1:
                    sh.del_worksheet(foglio_vuoto)
                    print(f"Foglio di default '{nome_predefinito}' eliminato con successo.")
            except gspread.exceptions.WorksheetNotFound:
                pass

        tutti_i_fogli = sh.worksheets()
        
        print("Controllo storico fogli (Max 10 consentiti)...")
        if len(tutti_i_fogli) > 10:
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