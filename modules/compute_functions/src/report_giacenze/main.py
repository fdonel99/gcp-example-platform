import datetime
import os
import pandas as pd
from google.cloud import bigquery
import google.auth
import gspread
from gspread_dataframe import set_with_dataframe
import functions_framework

@functions_framework.http
def report_giacenze(request):
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', '')
    
    if not project_id:
        return "Errore: GOOGLE_CLOUD_PROJECT non configurato.", 500

    dataset_table = 'NORTHSTAR.REPORT_GIACENZE'
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    
    if 'test' in project_id.lower():
        sheet_id = '1Ay1tjHrreEsM-Z1TBhnrg760czJSL9fOXt_VKtZDBeY' 
        sheet_name = f'REPORT_GIACENZE_TEST_{today_str}'
        print(f"Ambiente di TEST rilevato. Uso Sheet ID: {sheet_id}")
    else:
        sheet_id = '15O35KIgLTBjMj5XBxKxtL7a0w7gzbLV0rpX7-yeD1EQ'
        print(f"Ambiente di PROD rilevato. Uso Sheet ID: {sheet_id}")
        sheet_name = f'REPORT_FORNITORI_{today_str}'
    
    # 1. Questa query rimane invariata: salva su BigQuery il dettaglio per SINGOLA DATA
    sql_create_table = f"""
        CREATE OR REPLACE TABLE `{project_id}.{dataset_table}` AS (
            SELECT 
                d.sku,
                a.fornitore, 
                d.magazzino,
                d.DATA_MOVIMENTO,
                SUBSTR(d.DATA_MOVIMENTO, 1, 4) AS anno_movimento,
                SUBSTR(d.DATA_MOVIMENTO, 5, 2) AS mese_movimento,
                d.CLASSIFICAZIONE, 
                SUM(d.QTA) as tot_qta

            FROM  `{project_id}.NORTHSTAR.dbo_movimenti`
            LEFT JOIN `{project_id}.NORTHSTAR.ANAGRAFICA_PRODOTTO` a USING(sku)
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
                magazzino,
                anno_movimento,
                mese_movimento,
                CLASSIFICAZIONE, 
                SUM(tot_qta) AS tot_qta
            FROM `{project_id}.{dataset_table}`
            GROUP BY ALL
        """
        # ⬆️ FINE MODIFICA ⬆️
        
        df = bq_client.query(query_select).to_dataframe()

        print(f"DEBUG: DataFrame shape: {df.shape}")
        if df.empty:
            print("ATTENZIONE: Il DataFrame è vuoto!")
        else:
            print("Pulizia caratteri e NaN...")
            df = df.replace(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', regex=True)

        print(f"3. Connessione a Google Sheets...")
        credentials, _ = google.auth.default(scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(sheet_id)

        print(f"4. Creazione foglio: '{sheet_name}'...")
        
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
        for nome_predefinito in ["Foglio1", "Sheet1"]:
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

        messaggio = f"Successo! Dati caricati nel foglio '{sheet_name}'."
        print(messaggio)
        return (messaggio, 200)

    except Exception as e:
        errore = f"Si è verificato un errore: {str(e)}"
        print(errore)
        return (errore, 500)