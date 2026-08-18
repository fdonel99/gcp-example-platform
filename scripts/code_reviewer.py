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

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=llm_api_key,
)

# ==========================================
# 2. Tool: Leggi Git Diff (Modifiche Locali)
# ==========================================
def get_recent_diff():
    print("Recupero delle ultime modifiche del codice...")
    try:
        # Recupera le differenze dell'ultimo commit effettuato
        diff = subprocess.check_output(['git', 'diff', 'HEAD~1', 'HEAD'], text=True, stderr=subprocess.DEVNULL)
        return diff
    except Exception:
        print("Impossibile recuperare il diff (potrebbe essere il primo commit). Salto la review.")
        sys.exit(0)

# ==========================================
# 3. Tool: Invia Alert su Telegram
# ==========================================
def send_telegram_alert(testo_allarme):
    print("Invio alert su Telegram in corso...")
    messaggio = f"🚨 *ALLARME SICUREZZA PIPELINE* 🚨\n\nHo bloccato il deploy! Motivo:\n\n{testo_allarme}"
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": messaggio,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# ==========================================
# 4. Agente Revisore e Guardia
# ==========================================
def run_security_guard():
    diff_text = get_recent_diff()
    
    if not diff_text.strip():
        print("Nessuna differenza di codice rilevata. Via libera.")
        sys.exit(0)

    system_prompt = """Sei un Senior Cloud Security Architect e Terraform Expert.
Il tuo compito è analizzare questo Git Diff in cerca di PROBLEMI GRAVI.
Cerca ESCLUSIVAMENTE problemi critici come:
- Variabili hardcoded, password, token o secret in chiaro.
- Porte aperte al pubblico in modo molto pericoloso (es. SSH 22 su 0.0.0.0/0).
- Permessi IAM palesemente non sicuri.

REGOLE PER LA RISPOSTA:
1. Se il codice è sicuro, rispondi ESATTAMENTE E SOLO con la stringa: TUTTO_OK
2. Se trovi criticità gravi, scrivi un breve messaggio di alert (in italiano) per lo sviluppatore, spiegando qual è il rischio. Sii conciso."""

    print("Analisi di sicurezza in corso con LLM...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Ecco il git diff dell'ultimo push:\n\n{diff_text}"}
        ]
    )
    
    llm_reply = response.choices[0].message.content.strip()

    if llm_reply == "TUTTO_OK":
        print("✅ Controllo superato! L'agente non ha trovato problemi di sicurezza.")
        sys.exit(0) # Esci con 0: la pipeline prosegue!
    else:
        print("❌ CRITICITÀ RILEVATA! Blocco la pipeline e invio il messaggio...")
        send_telegram_alert(llm_reply)
        sys.exit(1) # Esci con 1: GITHUB ACTIONS FALLISCE E SI FERMA QUI!

# ==========================================
# 5. Esecuzione
# ==========================================
if __name__ == "__main__":
    run_security_guard()