import os
import json

# Importiamo i due moduli dell'architettura
from estrai_testo_e_coordinate import estrai_testo_e_coordinate
from agente_filtro import analizza_e_filtra

# ==========================================
# CONFIGURAZIONE AUTENTICAZIONE
# ==========================================
DIR_CORRENTE = os.path.dirname(os.path.abspath(__file__))
PERCORSO_CHIAVE = os.path.join(DIR_CORRENTE, "..", "local_tests_key.json")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = PERCORSO_CHIAVE

def main():
    percorso_immagine = os.path.join(DIR_CORRENTE, "esempio_infografica.jpg")
    
    try:
        # ---------------------------------------------------------
        # STEP 1: Estrazione dati grezzi (Coordinate, Stile, Colori)
        # ---------------------------------------------------------
        dati_strutturati = estrai_testo_e_coordinate(percorso_immagine)
        
        # ---------------------------------------------------------
        # STEP 2: Analisi Cognitiva (Cosa ignorare e che ruolo hanno)
        # ---------------------------------------------------------
        risultato_agente = analizza_e_filtra(percorso_immagine, dati_strutturati)
        
        # ---------------------------------------------------------
        # STAMPA DEI RISULTATI
        # ---------------------------------------------------------
        print("\n✅ RAGIONAMENTO AGENTE 1:")
        print(f"{risultato_agente.get('ragionamento')}\n")
        
        ids_da_ignorare = risultato_agente.get("ids_da_ignorare", [])
        
        # Creiamo un dizionario veloce per mappare l'ID al Ruolo assegnato da Gemini
        mappa_ruoli = {item["id_blocco"]: item["ruolo"] for item in risultato_agente.get("ruoli", [])}
        
        print("🎯 PIANO D'AZIONE PER L'INFOGRAFICA:")
        for blocco in dati_strutturati:
            id_b = blocco["id_blocco"]
            testo = " ".join([p["testo"] for p in blocco["parole"]])
            ruolo = mappa_ruoli.get(id_b, "Sconosciuto")
            
            if id_b in ids_da_ignorare:
                print(f"🔴 [ID: {id_b:02d}] IGNORA  | Ruolo: {ruolo.ljust(12)} | Testo: '{testo}'")
            else:
                print(f"🟢 [ID: {id_b:02d}] TRADUCI | Ruolo: {ruolo.ljust(12)} | Testo: '{testo}'")
        
    except Exception as e:
        print(f"\n❌ Errore critico durante l'esecuzione: {e}")

if __name__ == "__main__":
    main()