import os
import sys
import subprocess
import requests
from openai import OpenAI

# ==========================================
# 1. Configurazione Iniziale
# ==========================================
llm_api_key = os.getenv("LLM_API_KEY")
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

MODEL = "openai/gpt-4o"

if not all([llm_api_key, telegram_token, telegram_chat_id]):
    print("Errore: Variabili d'ambiente mancanti (LLM o Telegram).")
    sys.exit(1)

# OpenRouter consiglia di passare degli header extra per evitare blocchi
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=llm_api_key,
    default_headers={
        "HTTP-Referer": "https://tuosito.com", 
        "X-Title": "CI-CD-Security-Guard",
    }
)

# ==========================================
# 2. Tool: Leggi Git Diff
# ==========================================
def get_recent_diff():
    print("Recupero delle ultime modifiche del codice...")
    try:
        # Recupera le differenze dell'ultimo commit
        diff = subprocess.check_output(['git', 'diff', 'HEAD~1', 'HEAD'], text=True, stderr=subprocess.PIPE)
        return diff
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Impossibile recuperare il diff: {e.stderr.strip()}")
        print("Assicurati che la pipeline abbia scaricato la history (es. fetch-depth: 2). Salto la review.")
        sys.exit(0)

# ==========================================
# 3. Tool: Invia Alert su Telegram
# ==========================================
def send_telegram_alert(testo_allarme, severity="CRITICAL"):
    print("Invio alert su Telegram in corso...")
    
    # TRONCAMENTO SICUREZZA: Evita l'errore 400 causato dal limite di 4096 caratteri
    if len(testo_allarme) > 3900:
        testo_allarme = testo_allarme[:3900] + "\n\n[...Report troncato per limiti di spazio Telegram]"
        
    # Adatta il messaggio in base alla severità
    if severity == "WARNING":
        messaggio = f"⚠️ SEGNALAZIONE SICUREZZA PIPELINE ⚠️\n\nDeploy NON bloccato, ma richiede attenzione:\n\n{testo_allarme}"
    else:
        messaggio = f"🚨 ALLARME SICUREZZA PIPELINE 🚨\n\nHo BLOCCATO il deploy! Motivo:\n\n{testo_allarme}"
        
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    
    payload = {
        "chat_id": telegram_chat_id,
        "text": messaggio
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() 
        print("✅ Alert Telegram inviato con successo!")
    except Exception as e:
        print(f"❌ Errore durante l'invio dell'alert su Telegram: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Dettagli API Telegram: {e.response.text}")

# ==========================================
# 4. Agente Revisore
# ==========================================
def run_security_guard():
    diff_text = get_recent_diff()
    
    if not diff_text.strip():
        print("Nessuna differenza di codice rilevata. Via libera.")
        sys.exit(0)

    # Prompt aggiornato con i Tag espliciti per il parsing
    system_prompt = """Sei un Senior Cloud Security Architect e Terraform Expert.
Il tuo compito è analizzare questo Git Diff in cerca di problemi.

TASSONOMIA DEI PROBLEMI:
1. CRITICAL: Variabili hardcoded, password, token in chiaro, secret esposti, porte aperte al pubblico in modo pericoloso (es. SSH 0.0.0.0/0). (Questi bloccheranno il deploy).
2. WARNING: ID in chiaro, permessi IAM troppo ampi (es. documentai.apiUser o ruoli admin), o modifiche infrastrutturali dubbie. (Questi NON bloccheranno il deploy).
3. OK: Nessun problema di sicurezza rilevante.

REGOLE TASSATIVE PER LA RISPOSTA:
- Se il codice è sicuro, rispondi ESATTAMENTE E SOLO: [OK]
- Se trovi problemi di tipo WARNING, inizia TASSATIVAMENTE la risposta con: [WARNING] seguito dalla tua spiegazione.
- Se trovi problemi di tipo CRITICAL, inizia TASSATIVAMENTE la risposta con: [CRITICAL] seguito dalla tua spiegazione.

Sii conciso e scrivi in italiano."""

    print("Analisi di sicurezza in corso con LLM...")
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Ecco il git diff dell'ultimo push:\n\n{diff_text}"}
            ]
        )
        llm_reply = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Errore di connessione alle API LLM: {e}")
        sys.exit(1)

    # PARSING INTELLIGENTE BASATO SUI TAG
    reply_upper = llm_reply.upper()
    
    if reply_upper.startswith("[OK]") or reply_upper == "OK":
        print("✅ Controllo superato! L'agente non ha trovato problemi di sicurezza.")
        sys.exit(0)
        
    elif reply_upper.startswith("[WARNING]"):
        print("⚠️ SEGNALAZIONE RILEVATA (WARNING). La pipeline NON verrà bloccata.")
        # Rimuoviamo il tag "[WARNING]" iniziale dal messaggio per pulirlo
        clean_reply = llm_reply[9:].strip() if reply_upper.startswith("[WARNING]") else llm_reply
        send_telegram_alert(clean_reply, severity="WARNING")
        sys.exit(0) # EXIT 0 -> LA PIPELINE PROSEGUE CON SUCCESSO!
        
    else:
        # Tutto il resto è considerato CRITICAL (di default)
        print("❌ CRITICITÀ RILEVATA (CRITICAL). Blocco la pipeline!")
        clean_reply = llm_reply[10:].strip() if reply_upper.startswith("[CRITICAL]") else llm_reply
        send_telegram_alert(clean_reply, severity="CRITICAL")
        sys.exit(1) # EXIT 1 -> LA PIPELINE FALLISCE!

if __name__ == "__main__":
    run_security_guard()