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
    # 1. Lettura del project_id
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', '')
    
    if not project_id:
        return "Errore: GOOGLE_CLOUD_PROJECT non configurato.", 500

    dataset_table = 'NORTHSTAR.REPORT_GIACENZE'
    
    # 2. Impostazione dell'ID del Google Sheet
    if 'test' in project_id.lower():
        sheet_id = '1Ay1tjHrreEsM-Z1TBhnrg760czJSL9fOXt_VKtZDBeY' 
        print(f"Ambiente di TEST rilevato. Uso Sheet ID: {sheet_id}")
    else:
        sheet_id = '15O35KIgLTBjMj5XBxKxtL7a0w7gzbLV0rpX7-yeD1EQ'
        print(f"Ambiente di PROD rilevato. Uso Sheet ID: {sheet_id}")
    
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    sheet_name = f'REPORT_GIACENZE_{today_str}'

    # === LA TUA QUERY SQL CON LTRIM SU SKU ===
    sql_create_table = f"""
        CREATE OR REPLACE TABLE `{project_id}.{dataset_table}` AS (
            SELECT 
                d.sku,
                a.fornitore, 
                d.magazzino,
                d.DATA_MOVIMENTO,
                d.CLASSIFICAZIONE, 
                SUM(d.QTA) as tot_qta
            FROM (
                SELECT * REPLACE(LTRIM(sku) AS sku)
                FROM `{project_id}.NORTHSTAR.dbo_movimenti`
            ) d 
            LEFT JOIN (
                SELECT * REPLACE(LTRIM(sku) AS sku)
                FROM `{project_id}.NORTHSTAR.ANAGRAFICA_PRODOTTO`
            ) a USING(sku)
            GROUP BY ALL
        );
    """

    try:
        # FASE 1: Ricrea tabella su BQ
        bq_client = bigquery.Client(project=project_id)
        print("1. Ricreazione tabella su BigQuery in corso...")
        bq_client.query(sql_create_table).result()
        print("Tabella creata con successo.")

        # FASE 2: Estrazione dati
        print("2. Scaricamento dati nel dataframe...")
        query_select = f"SELECT * FROM `{project_id}.{dataset_table}`"
        df = bq_client.query(query_select).to_dataframe()

        print(f"DEBUG: DataFrame shape: {df.shape}")
        if df.empty:
            print("ATTENZIONE: Il DataFrame è vuoto!")
        else:
            print("Pulizia caratteri e NaN...")
            df = df.replace(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', regex=True)

        # FASE 3: Connessione a GSheets
        print(f"3. Connessione a Google Sheets...")
        credentials, _ = google.auth.default(scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(sheet_id)

        # FASE 4: Scrittura foglio odierno
        print(f"4. Creazione foglio: '{sheet_name}'...")
        
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
        set_with_dataframe(worksheet_oggi, df, include_index=False, include_column_header=True)
        print("Scrittura completata.")

        # FASE 5: Pulizia
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