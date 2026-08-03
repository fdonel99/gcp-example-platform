import functions_framework
import pandas as pd
import numpy as np
import re
import os
from google.cloud import storage
import google.auth
import gspread
from gspread_dataframe import get_as_dataframe

# --- CONFIGURAZIONE GOOGLE SHEETS ---
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1TYpxmD6H_9v-ZeeOqSZqiHF50cyzj6xpg51zTaTEQWE')
credentials, _ = google.auth.default(scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(credentials)


def estrai_dimensioni(testo):
    """
    Estrae le tre dimensioni principali da una stringa di testo usando espressioni regolari.
    Gestisce anche il formato con diametro 'Ø'.
    """
    if pd.isna(testo):
        return pd.Series([np.nan, np.nan, np.nan])
    testo_str = str(testo)
    numeri = re.findall(r'\d+(?:,\d+)?', testo_str)
    if len(numeri) >= 3:
        return pd.Series([numeri[0], numeri[1], numeri[2]])
    elif len(numeri) == 2 and 'Ø' in testo_str.upper():
        return pd.Series([numeri[0], numeri[0], numeri[1]])
    elif len(numeri) == 2:
        return pd.Series([numeri[0], numeri[1], np.nan])
    elif len(numeri) == 1:
        return pd.Series([numeri[0], np.nan, np.nan])
    else:
        return pd.Series([np.nan, np.nan, np.nan])

def correggi_peso(val):
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    testo = str(val).strip()
    testo = re.sub(r'[a-zA-Z\s]', '', testo)
    if '.' in testo and ',' in testo:
        testo = testo.replace('.', '')
        testo = testo.replace(',', '.')
    elif ',' in testo:
        testo = testo.replace(',', '.')
    elif '.' in testo:
        if bool(re.search(r'\.\d{3}$', testo)):
            testo = testo.replace('.', '')
    try:
        return float(testo)
    except ValueError:
        return 0.0


def assegna_CLASSE(row):
    """
    Assegna la classe di spedizione Amazon in base alle dimensioni, al peso e alla tabella di riferimento.
    """
    dims = sorted([row['DIMENSIONE_1'], row['DIMENSIONE_2'], row['DIMENSIONE_3']])
    dim_min = dims[0]
    dim_mid = dims[1]
    dim_max = dims[2]
    peso = row['PESO X AMAZON']
    peso_vol = row.get('PESO_DIMENSIONALE', 0)
    tabella = row.get('TABELLA')
    
    if tabella == 'B':
        if dim_min <= 7 and dim_mid <= 25 and dim_max <= 35 and peso <= 3900:
            return "Pacco piccolo 1"
        elif dim_min <= 9 and dim_mid <= 25 and dim_max <= 35 and peso <= 3900:
            return "Pacco piccolo 2"
        elif dim_min <= 12 and dim_mid <= 25 and dim_max <= 35 and peso <= 3900:
            return "Pacco piccolo 3"
        elif dim_min <= 6 and dim_mid <= 30 and dim_max <= 40 and peso <= 11900:
            return "Pacco medio 1"
        elif dim_min <= 20 and dim_mid <= 30 and dim_max <= 40 and peso <= 11900:
            return "Pacco medio 2"
        elif dim_min <= 10 and dim_mid <= 34 and dim_max <= 45 and peso <= 11900:
            return "Pacco grande 1"
        elif dim_min <= 26 and dim_mid <= 34 and dim_max <= 45 and peso <= 11900:
            return "Pacco grande 2"
        else:
            return "Tipo B - Fuori range / Non classificato"

    elif tabella == 'A':
        if dim_min <= 2.5 and dim_mid <= 23 and dim_max <= 33 and peso <= 100:
            return "Busta leggera"
        elif dim_min <= 2.5 and dim_mid <= 23 and dim_max <= 33 and peso <= 460:
            return "Busta standard"
        elif dim_min <= 4 and dim_mid <= 23 and dim_max <= 33 and peso <= 960:
            return "Busta grande"
        elif dim_min <= 6 and dim_mid <= 23 and dim_max <= 33 and peso <= 960:
            return "Busta extra large"
        elif dim_min <= 12 and dim_mid <= 25 and dim_max <= 35 and peso <= 3900 and peso_vol <= 2100:
            return "Pacco piccolo"
        elif dim_min <= 26 and dim_mid <= 34 and dim_max <= 45 and peso <= 11900 and peso_vol <= 7960:
            return "Pacco standard"
        elif dim_min <= 46 and dim_mid <= 46 and dim_max <= 61 and peso <= 1760 and peso_vol <= 25820:
            return "Fuori misura piccolo"
        elif dim_min <= 60 and dim_mid <= 60 and dim_max <= 101 and peso <= 15000 and peso_vol <= 72720:
            return "Fuori misura standard leggero"
        elif dim_min <= 60 and dim_mid <= 60 and dim_max <= 101 and peso <= 23000 and peso_vol <= 72720:
            return "Fuori misura standard pesante"
        elif dim_min <= 60 and dim_mid <= 60 and dim_max <= 120 and peso <= 23000 and peso_vol <= 86400:
            return "Fuori misura standard grande"
        elif dim_min <= 60 and dim_mid <= 60 and dim_max <= 120 and peso <= 23000 and peso_vol <= 126000:
            return "Fuori misura ingombrante"
        elif peso <= 31500 and peso_vol <= 126000:
            return "Fuori misura pesante"
        else:
            return "Tipo A - Fuori range / Non classificato"
    return "Tabella sconosciuta"


def calcolo_trasporto_it_de(df_spese_trasporto, df_costi_A, df_costi_B):
    gruppo_buste_standard_A = [
        "Busta leggera", "Busta grande", "Busta standard",
        "Busta extra large", "Pacco piccolo", "Pacco standard"
    ]
    gruppo_fuori_misura_A = [
        "Fuori misura piccolo", "Fuori misura standard leggero",
        "Fuori misura standard pesante", "Fuori misura standard grande",
        "Fuori misura ingombrante", "Fuori misura pesante"
    ]
    gruppo_pacchi_B = [
        "Pacco piccolo 1", "Pacco piccolo 2", "Pacco piccolo 3",
        "Pacco medio 1", "Pacco medio 2", "Pacco grande 1", "Pacco grande 2"
    ]

    df_spese_A = df_spese_trasporto[df_spese_trasporto['TABELLA'] == 'A'].copy()
    df_spese_B = df_spese_trasporto[df_spese_trasporto['TABELLA'] == 'B'].copy()

    df_costi_A_clean = df_costi_A.rename(columns={'dimensioni': 'CLASSE', 'peso': 'peso_trasporto'})
    colonne_A = ['CLASSE', 'peso_trasporto', 'IT_EUR', 'incremento_IT_EUR', 'DE_EUR', 'incremento_DE_EUR']
    df_costi_A_ridotto = df_costi_A_clean[colonne_A]

    df_joined_A = pd.merge(df_spese_A, df_costi_A_ridotto, on='CLASSE', how='left')

    matched_A = df_joined_A[df_joined_A['peso_trasporto'].notna()].copy()
    unmatched_A = df_joined_A[df_joined_A['peso_trasporto'].isna()].copy()

    matched_A = matched_A[
        (matched_A['peso_trasporto'] >= matched_A['PESO X AMAZON']) |
        (matched_A['CLASSE'].isin(gruppo_fuori_misura_A))
    ]
    matched_A = matched_A.sort_values(by=['SKU', 'peso_trasporto'])
    matched_A = matched_A.drop_duplicates(subset=['SKU'], keep='first')

    df_joined_A_filtered = pd.concat([matched_A, unmatched_A], ignore_index=True)

    df_costi_B_clean = df_costi_B.rename(columns={'dimensioni': 'CLASSE', 'peso': 'peso_trasporto'})
    colonne_B = ['CLASSE', 'peso_trasporto', 'IT_EUR', 'incremento_IT_EUR', 'DE_EUR', 'incremento_DE_EUR']
    df_costi_B_ridotto = df_costi_B_clean[colonne_B]

    df_joined_B = pd.merge(df_spese_B, df_costi_B_ridotto, on='CLASSE', how='left')
    
    # FIX: De-duplicazione per la Tabella B
    matched_B = df_joined_B[df_joined_B['peso_trasporto'].notna()].copy()
    unmatched_B = df_joined_B[df_joined_B['peso_trasporto'].isna()].copy()
    matched_B = matched_B[matched_B['peso_trasporto'] >= matched_B['PESO X AMAZON']]
    matched_B = matched_B.sort_values(by=['SKU', 'peso_trasporto'])
    matched_B = matched_B.drop_duplicates(subset=['SKU'], keep='first')
    df_joined_B = pd.concat([matched_B, unmatched_B], ignore_index=True)

    colonne_da_azzerare = ['peso_trasporto', 'IT_EUR', 'incremento_IT_EUR', 'DE_EUR', 'incremento_DE_EUR']
    df_joined_A_filtered[colonne_da_azzerare] = df_joined_A_filtered[colonne_da_azzerare].fillna(0)
    df_joined_B[colonne_da_azzerare] = df_joined_B[colonne_da_azzerare].fillna(0)

    df_finale = pd.concat([df_joined_A_filtered, df_joined_B], ignore_index=True)
    
    # FIX: Calcolo degli scatti di peso corretti (100g e 1kg)
    differenza_grammi = df_finale['PESO X AMAZON'] - df_finale['peso_trasporto']
    df_finale['scatti_kg'] = np.where(differenza_grammi > 0, np.ceil(differenza_grammi / 1000), 0)
    df_finale['scatti_100g'] = np.where(differenza_grammi > 0, np.ceil(differenza_grammi / 100), 0)

    condizioni = [
        df_finale['CLASSE'].isin(gruppo_buste_standard_A),
        df_finale['CLASSE'].isin(gruppo_fuori_misura_A),
        df_finale['CLASSE'].isin(gruppo_pacchi_B)
    ]

    calcoli_it = [
        df_finale['IT_EUR'],
        df_finale['IT_EUR'] + (df_finale['scatti_kg'] * df_finale['incremento_IT_EUR']),
        df_finale['IT_EUR'] + (df_finale['scatti_100g'] * df_finale['incremento_IT_EUR'])
    ]
    calcoli_de = [
        df_finale['DE_EUR'],
        df_finale['DE_EUR'] + (df_finale['scatti_kg'] * df_finale['incremento_DE_EUR']),
        df_finale['DE_EUR'] + (df_finale['scatti_100g'] * df_finale['incremento_DE_EUR'])
    ]

    df_finale['Trasporto IT'] = np.select(condizioni, calcoli_it, default=0)
    df_finale['Trasporto DE'] = np.select(condizioni, calcoli_de, default=0)

    df_finale = df_finale.sort_values(by='PESO X AMAZON', ascending=False).reset_index(drop=True)
    return df_finale


def calcolo_trasporto_fr(df_spese_trasporto, df_costi_A, df_costi_B):
    gruppo_buste_standard_A = [
        "Busta leggera", "Busta grande", "Busta standard",
        "Busta extra large", "Pacco piccolo", "Pacco standard"
    ]
    gruppo_fuori_misura_A = [
        "Fuori misura piccolo", "Fuori misura standard leggero",
        "Fuori misura standard pesante", "Fuori misura standard grande",
        "Fuori misura ingombrante", "Fuori misura pesante"
    ]
    gruppo_pacchi_B = [
        "Pacco piccolo 1", "Pacco piccolo 2", "Pacco piccolo 3",
        "Pacco medio 1", "Pacco medio 2", "Pacco grande 1", "Pacco grande 2"
    ]

    df_spese_A = df_spese_trasporto[df_spese_trasporto['TABELLA'] == 'A'].copy()
    df_spese_B = df_spese_trasporto[df_spese_trasporto['TABELLA'] == 'B'].copy()

    df_costi_A_clean = df_costi_A.rename(columns={'dimensioni': 'CLASSE', 'peso': 'peso_trasporto'})
    colonne_A = ['CLASSE', 'peso_trasporto', 'CEP_IT_ES_FR_EUR', 'incremento_CEP_IT_ES_FR_EUR']
    df_costi_A_ridotto = df_costi_A_clean[colonne_A]

    df_joined_A = pd.merge(df_spese_A, df_costi_A_ridotto, on='CLASSE', how='left')
    matched_A = df_joined_A[df_joined_A['peso_trasporto'].notna()].copy()
    unmatched_A = df_joined_A[df_joined_A['peso_trasporto'].isna()].copy()

    matched_A = matched_A[
        (matched_A['peso_trasporto'] >= matched_A['PESO X AMAZON']) |
        (matched_A['CLASSE'].isin(gruppo_fuori_misura_A))
    ]
    matched_A = matched_A.sort_values(by=['SKU', 'peso_trasporto'])
    matched_A = matched_A.drop_duplicates(subset=['SKU'], keep='first')

    df_joined_A_filtered = pd.concat([matched_A, unmatched_A], ignore_index=True)
    df_joined_A_filtered = df_joined_A_filtered.rename(columns={
        'CEP_IT_ES_FR_EUR': 'FR_EUR',
        'incremento_CEP_IT_ES_FR_EUR': 'incremento_FR_EUR'
    })

    df_costi_B_clean = df_costi_B.rename(columns={'dimensioni': 'CLASSE', 'peso': 'peso_trasporto'})
    colonne_B = ['CLASSE', 'peso_trasporto', 'FR_EUR', 'incremento_FR_EUR']
    df_costi_B_ridotto = df_costi_B_clean[colonne_B]

    df_joined_B = pd.merge(df_spese_B, df_costi_B_ridotto, on='CLASSE', how='left')
    
    # FIX: De-duplicazione per la Tabella B
    matched_B = df_joined_B[df_joined_B['peso_trasporto'].notna()].copy()
    unmatched_B = df_joined_B[df_joined_B['peso_trasporto'].isna()].copy()
    matched_B = matched_B[matched_B['peso_trasporto'] >= matched_B['PESO X AMAZON']]
    matched_B = matched_B.sort_values(by=['SKU', 'peso_trasporto'])
    matched_B = matched_B.drop_duplicates(subset=['SKU'], keep='first')
    df_joined_B = pd.concat([matched_B, unmatched_B], ignore_index=True)
    
    colonne_da_azzerare = ['peso_trasporto', 'FR_EUR', 'incremento_FR_EUR']
    df_joined_A_filtered[colonne_da_azzerare] = df_joined_A_filtered[colonne_da_azzerare].fillna(0)
    df_joined_B[colonne_da_azzerare] = df_joined_B[colonne_da_azzerare].fillna(0)

    df_finale_fr = pd.concat([df_joined_A_filtered, df_joined_B], ignore_index=True)
    
    # FIX: Calcolo degli scatti di peso corretti (100g e 1kg)
    differenza_grammi = df_finale_fr['PESO X AMAZON'] - df_finale_fr['peso_trasporto']
    df_finale_fr['scatti_kg'] = np.where(differenza_grammi > 0, np.ceil(differenza_grammi / 1000), 0)
    df_finale_fr['scatti_100g'] = np.where(differenza_grammi > 0, np.ceil(differenza_grammi / 100), 0)

    condizioni = [
        df_finale_fr['CLASSE'].isin(gruppo_buste_standard_A),
        df_finale_fr['CLASSE'].isin(gruppo_fuori_misura_A),
        df_finale_fr['CLASSE'].isin(gruppo_pacchi_B)
    ]

    calcoli_fr = [
        df_finale_fr['FR_EUR'],
        df_finale_fr['FR_EUR'] + (df_finale_fr['scatti_kg'] * df_finale_fr['incremento_FR_EUR']),
        df_finale_fr['FR_EUR'] + (df_finale_fr['scatti_100g'] * df_finale_fr['incremento_FR_EUR'])
    ]

    df_finale_fr['Trasporto FR'] = np.select(condizioni, calcoli_fr, default=0)
    df_finale_fr = df_finale_fr.sort_values(by='PESO X AMAZON', ascending=False).reset_index(drop=True)
    return df_finale_fr


def calcolo_trasporto_sp(df_spese_trasporto, df_costi_A, df_costi_B):
    gruppo_buste_standard_A = [
        "Busta leggera", "Busta grande", "Busta standard",
        "Busta extra large", "Pacco piccolo", "Pacco standard"
    ]
    gruppo_fuori_misura_A = [
        "Fuori misura piccolo", "Fuori misura standard leggero",
        "Fuori misura standard pesante", "Fuori misura standard grande",
        "Fuori misura ingombrante", "Fuori misura pesante"
    ]
    gruppo_pacchi_B = [
        "Pacco piccolo 1", "Pacco piccolo 2", "Pacco piccolo 3",
        "Pacco medio 1", "Pacco medio 2", "Pacco grande 1", "Pacco grande 2"
    ]

    df_spese_A = df_spese_trasporto[df_spese_trasporto['TABELLA'] == 'A'].copy()
    df_spese_B = df_spese_trasporto[df_spese_trasporto['TABELLA'] == 'B'].copy()

    df_costi_A_clean = df_costi_A.rename(columns={'dimensioni': 'CLASSE', 'peso': 'peso_trasporto'})
    colonne_A = ['CLASSE', 'peso_trasporto', 'CEP_IT_ES_FR_EUR', 'incremento_CEP_IT_ES_FR_EUR']
    df_costi_A_ridotto = df_costi_A_clean[colonne_A]

    df_joined_A = pd.merge(df_spese_A, df_costi_A_ridotto, on='CLASSE', how='left')
    matched_A = df_joined_A[df_joined_A['peso_trasporto'].notna()].copy()
    unmatched_A = df_joined_A[df_joined_A['peso_trasporto'].isna()].copy()

    matched_A = matched_A[
        (matched_A['peso_trasporto'] >= matched_A['PESO X AMAZON']) |
        (matched_A['CLASSE'].isin(gruppo_fuori_misura_A))
    ]
    matched_A = matched_A.sort_values(by=['SKU', 'peso_trasporto'])
    matched_A = matched_A.drop_duplicates(subset=['SKU'], keep='first')

    df_joined_A_filtered = pd.concat([matched_A, unmatched_A], ignore_index=True)
    df_joined_A_filtered = df_joined_A_filtered.rename(columns={
        'CEP_IT_ES_FR_EUR': 'ES_EUR',
        'incremento_CEP_IT_ES_FR_EUR': 'incremento_ES_EUR'
    })

    df_costi_B_clean = df_costi_B.rename(columns={'dimensioni': 'CLASSE', 'peso': 'peso_trasporto'})
    colonne_B = ['CLASSE', 'peso_trasporto', 'ES_EUR', 'incremento_ES_EUR']
    df_costi_B_ridotto = df_costi_B_clean[colonne_B]

    df_joined_B = pd.merge(df_spese_B, df_costi_B_ridotto, on='CLASSE', how='left')
    
    # FIX: De-duplicazione per la Tabella B
    matched_B = df_joined_B[df_joined_B['peso_trasporto'].notna()].copy()
    unmatched_B = df_joined_B[df_joined_B['peso_trasporto'].isna()].copy()
    matched_B = matched_B[matched_B['peso_trasporto'] >= matched_B['PESO X AMAZON']]
    matched_B = matched_B.sort_values(by=['SKU', 'peso_trasporto'])
    matched_B = matched_B.drop_duplicates(subset=['SKU'], keep='first')
    df_joined_B = pd.concat([matched_B, unmatched_B], ignore_index=True)

    colonne_da_azzerare = ['peso_trasporto', 'ES_EUR', 'incremento_ES_EUR']
    df_joined_A_filtered[colonne_da_azzerare] = df_joined_A_filtered[colonne_da_azzerare].fillna(0)
    df_joined_B[colonne_da_azzerare] = df_joined_B[colonne_da_azzerare].fillna(0)

    df_finale_sp = pd.concat([df_joined_A_filtered, df_joined_B], ignore_index=True)
    
    # FIX: Calcolo degli scatti di peso corretti (100g e 1kg)
    differenza_grammi = df_finale_sp['PESO X AMAZON'] - df_finale_sp['peso_trasporto']
    df_finale_sp['scatti_kg'] = np.where(differenza_grammi > 0, np.ceil(differenza_grammi / 1000), 0)
    df_finale_sp['scatti_100g'] = np.where(differenza_grammi > 0, np.ceil(differenza_grammi / 100), 0)

    condizioni = [
        df_finale_sp['CLASSE'].isin(gruppo_buste_standard_A),
        df_finale_sp['CLASSE'].isin(gruppo_fuori_misura_A),
        df_finale_sp['CLASSE'].isin(gruppo_pacchi_B)
    ]

    calcoli_sp = [
        df_finale_sp['ES_EUR'],
        df_finale_sp['ES_EUR'] + (df_finale_sp['scatti_kg'] * df_finale_sp['incremento_ES_EUR']),
        df_finale_sp['ES_EUR'] + (df_finale_sp['scatti_100g'] * df_finale_sp['incremento_ES_EUR'])
    ]

    df_finale_sp['Trasporto SP'] = np.select(condizioni, calcoli_sp, default=0)
    df_finale_sp = df_finale_sp.sort_values(by='PESO X AMAZON', ascending=False).reset_index(drop=True)
    return df_finale_sp


def elabora_costi_logistici(input_path, output_path):
    """
    Funzione principale. Legge l'Excel da locale e i costi da Google Sheets.
    """
    print(f"Caricamento file di input: {input_path}...")
    # 1. Lettura 'grezza' per ignorare eventuali righe vuote iniziali
    df = pd.read_excel(input_path, header=None)
    df = df.dropna(how='all')
    if not df.empty:
        nuove_colonne = df.iloc[0]
        df.columns = nuove_colonne
        df = df.iloc[1:].reset_index(drop=True)

    df.columns = df.columns.astype(str).str.upper().str.strip()
    print("Estrazione e pulizia delle dimensioni...")
    df[['DIMENSIONE_1', 'DIMENSIONE_2', 'DIMENSIONE_3']] = df['DIMENSIONI'].apply(estrai_dimensioni)

    for col in ['DIMENSIONE_1', 'DIMENSIONE_2', 'DIMENSIONE_3']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    df["PESO_DIMENSIONALE"] = (df["DIMENSIONE_1"] * df["DIMENSIONE_2"] * df["DIMENSIONE_3"]) / 5
    
    # === CORREZIONE PESO ===
    df["PESO"] = df["PESO"].apply(correggi_peso)
    if 'TABELLA' in df.columns:
        df['TABELLA'] = df['TABELLA'].replace(r'^\s*$', np.nan, regex=True).fillna("A")
    else:
        df["TABELLA"] = "A"

    print("Calcolo del PESO X AMAZON (peso di fatturazione)...")
    df["PESO X AMAZON"] = np.where(
        df["TABELLA"] == 'B',
        df["PESO_DIMENSIONALE"],
        df[["PESO_DIMENSIONALE", "PESO"]].max(axis=1)
    )

    print(f"Caricamento tabelle di costo dal Google Sheet ({SPREADSHEET_ID})...")
    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        df_fr_sp_A_data = get_as_dataframe(spreadsheet.worksheet("FR_SP_A")).dropna(how='all', axis=0).dropna(how='all', axis=1)
        df_it_de_A_data = get_as_dataframe(spreadsheet.worksheet("IT_DE_A")).dropna(how='all', axis=0).dropna(how='all', axis=1)
        df_fr_sp_B_data = get_as_dataframe(spreadsheet.worksheet("FR_SP_B")).dropna(how='all', axis=0).dropna(how='all', axis=1)
        df_it_de_B_data = get_as_dataframe(spreadsheet.worksheet("IT_DE_B")).dropna(how='all', axis=0).dropna(how='all', axis=1)
    except Exception as e:
        print(f"Errore durante la lettura da Google Sheets: {e}")
        raise e

    # Assegnazione classi
    print("Assegnazione classe logistica...")
    df['CLASSE'] = df.apply(assegna_CLASSE, axis=1)

    df_spese_trasporto = df[['PESO X AMAZON', 'SKU', 'CLASSE', 'TABELLA']].copy()
    df_spese_trasporto = df_spese_trasporto.dropna(subset=['SKU'])
    
    # Calcolo trasporti IT e DE
    print("Calcolo costi di trasporto per Italia e Germania...")
    df_calcolo_it_de = calcolo_trasporto_it_de(df_spese_trasporto, df_it_de_A_data, df_it_de_B_data)
    df_costi_finali = df_calcolo_it_de[['SKU', 'CLASSE', 'Trasporto IT', 'Trasporto DE']].copy()

    colonne_da_rimuovere = [col for col in ['Trasporto IT', 'Trasporto DE', 'Trsporto DE'] if col in df.columns]
    if colonne_da_rimuovere:
        df = df.drop(columns=colonne_da_rimuovere)

    df = pd.merge(df, df_costi_finali, on=['SKU', 'CLASSE'], how='left')
    df['Trasporto IT'] = df['Trasporto IT'].fillna(0)
    df['Trasporto DE'] = df['Trasporto DE'].fillna(0)

    # Calcolo trasporto FR
    print("Calcolo costi di trasporto per la Francia...")
    df_calcolo_fr = calcolo_trasporto_fr(df_spese_trasporto, df_fr_sp_A_data, df_fr_sp_B_data)
    df_costi_fr_finali = df_calcolo_fr[['SKU', 'CLASSE', 'Trasporto FR']].copy()
    df = df.drop(columns=['Trasporto FR'], errors='ignore')
    df = pd.merge(df, df_costi_fr_finali, on=['SKU', 'CLASSE'], how='left')
    df['Trasporto FR'] = df['Trasporto FR'].fillna(0)

    # Calcolo trasporto SP
    print("Calcolo costi di trasporto per la Spagna...")
    df_calcolo_sp = calcolo_trasporto_sp(df_spese_trasporto, df_fr_sp_A_data, df_fr_sp_B_data)
    df_costi_sp_finali = df_calcolo_sp[['SKU', 'CLASSE', 'Trasporto SP']].copy()
    df = df.drop(columns=['Trasporto SP'], errors='ignore')
    df = pd.merge(df, df_costi_sp_finali, on=['SKU', 'CLASSE'], how='left')
    df['Trasporto SP'] = df['Trasporto SP'].fillna(0)

    print("Pulizia delle colonne vuote / UNNAMED...")
    colonne_unnamed = [col for col in df.columns if 'UNNAMED' in str(col)]
    if colonne_unnamed:
        df = df.drop(columns=colonne_unnamed)
    
    df = df.dropna(axis=1, how='all')
    print(f"Salvataggio del file elaborato in: {output_path}")
    df.to_excel(output_path, index=False)
    print("Elaborazione interna completata con successo!")

@functions_framework.cloud_event
def calcola_spese_trasporto(cloud_event):
    """
    Trigger invocato da Google Cloud Storage al caricamento di un file.
    Utilizza la directory /tmp/ per lavorare i file Excel in sicurezza.
    """
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    # CONTROLLO ANTI-LOOP INFINITO
    if "_elaborato" in file_name:
        print(f"[{file_name}] è un file elaborato. Salto per evitare loop infiniti.")
        return

    print(f"Nuovo file rilevato: gs://{bucket_name}/{file_name}")

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    base_name = os.path.basename(file_name)
    name_without_ext, ext = os.path.splitext(base_name)
    local_input = f"/tmp/{base_name}"
    local_output = f"/tmp/{name_without_ext}_elaborato{ext}"
    output_gcs_name = file_name.replace(ext, f"_elaborato{ext}")

    try:
        # Scarica il file localmente
        print(f"Scaricamento del file in {local_input}...")
        blob.download_to_filename(local_input)
        
        # Avvia l'elaborazione usando i percorsi locali
        elabora_costi_logistici(local_input, local_output)
        
        # Ricarica il risultato sul bucket
        print(f"Caricamento del file elaborato come gs://{bucket_name}/{output_gcs_name}...")
        output_blob = bucket.blob(output_gcs_name)
        output_blob.upload_from_filename(local_output)
        
        # Elimina il file originale
        print(f"Eliminazione del file originale: {file_name}")
        blob.delete()
        print("Processo terminato con successo.")

    except Exception as e:
        print(f"Errore durante l'elaborazione: {str(e)}")
        raise e