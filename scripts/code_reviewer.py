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
        "HTTP-Referer": "https://tuosito.com", # Inserisci un URL reale o fittizio
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
def send_telegram_alert(testo_allarme):
    print("Invio alert su Telegram in corso...")
    
    # TRONCAMENTO SICUREZZA: Evita l'errore 400 causato dal limite di 4096 caratteri
    if len(testo_allarme) > 3900:
        testo_allarme = testo_allarme[:3900] + "\n\n[...Report troncato per limiti di spazio Telegram]"
        
    messaggio = f"🚨 ALLARME SICUREZZA PIPELINE 🚨\n\nHo bloccato il deploy! Motivo:\n\n{testo_allarme}"
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    
    # RIMOSSO parse_mode: "Markdown" per evitare crash causati dalla formattazione imprevedibile dell'LLM
    payload = {
        "chat_id": telegram_chat_id,
        "text": messaggio
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() # Lancia un'eccezione se Telegram risponde con un errore
        print("✅ Alert Telegram inviato con successo!")
    except Exception as e:
        print(f"❌ Errore durante l'invio dell'alert su Telegram: {e}")
        # Stampa il corpo della risposta di Telegram per un debug più facile
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

    system_prompt = """Sei un Senior Cloud Security Architect e Terraform Expert.
Il tuo compito è analizzare questo Git Diff in cerca di PROBLEMI GRAVI.
Cerca ESCLUSIVAMENTE problemi critici come:
- Variabili hardcoded, password, token o secret in chiaro.
- Porte aperte al pubblico in modo molto pericoloso (es. SSH 22 su 0.0.0.0/0).

Tutte le CHIAVI API devono generare un BLOCCO DEL DEPLOY e un ALERT su Telegram. 
Gli ID, invece, devono essere segnalati ma non bloccare il deploy.
Anche i permessi IAM non sicuri devono essere segnalati ma non bloccare il deploy.

REGOLE PER LA RISPOSTA:
1. Se il codice è sicuro, rispondi ESATTAMENTE E SOLO con la stringa: TUTTO_OK
2. Se trovi criticità gravi, scrivi un breve messaggio di alert (in italiano) per lo sviluppatore, spiegando qual è il rischio. Sii conciso."""

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
        sys.exit(1) # Decidi tu: exit(1) blocca la pipeline se l'LLM è down, exit(0) la fa passare.

    # Controllo più tollerante per evitare falsi positivi da punteggiatura
    if "TUTTO_OK" in llm_reply.upper():
        print("✅ Controllo superato! L'agente non ha trovato problemi di sicurezza.")
        sys.exit(0)
    else:
        print("❌ CRITICITÀ RILEVATA! Blocco la pipeline e invio il messaggio...")
        send_telegram_alert(llm_reply)
        sys.exit(1)

if __name__ == "__main__":
    run_security_guard()