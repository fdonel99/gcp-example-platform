import os
import glob
import hashlib
import json
from datetime import datetime
from openai import OpenAI

# ==========================================
# 1. Configurazione Iniziale
# ==========================================
api_key = os.getenv("LLM_API_KEY")
env = os.getenv("ENVIRONMENT", "sconosciuto") # Sarà 'prod' o 'test'
MODEL = "anthropic/claude-3.5-sonnet"

# Rinominiamo il file di stato in base all'ambiente per evitare sovrapposizioni
STATE_FILE = f".docs_state_{env}.json"
# Definiamo la cartella dinamica in base all'ambiente
DOCS_DIR = f"docs/{env}"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# ==========================================
# 2. Funzioni di Supporto (Stato e Data)
# ==========================================
def get_hash(text):
    """Genera un'impronta digitale del testo per rilevare i cambiamenti."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_state():
    """Carica gli hash della run precedente."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(state):
    """Salva gli hash della run corrente."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_header(titolo):
    """Genera l'intestazione standard con data e ora italiane."""
    # Nota: su GitHub Actions l'orario sarà UTC, formattiamo in modo chiaro
    now = datetime.now().strftime("%d/%m/%Y alle %H:%M:%S (UTC)")
    return f"# {titolo}\n\n*Ultimo aggiornamento automatico: {now} (Deploy in ambiente: **{env}**)*\n\n---\n\n"

# ==========================================
# 3. Funzioni di Lettura del Contesto
# ==========================================
def get_project_structure(root_dir="."):
    ignore_dirs = ['.git', '.terraform', 'node_modules', '__pycache__', 'docs', 'scripts']
    tree_lines = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        tree_lines.append(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if not f.startswith('.'):
                tree_lines.append(f"{subindent}{f}")
    return "\n".join(tree_lines)

def get_terraform_code():
    tf_files = glob.glob("**/*.tf", recursive=True)
    content = ""
    for file in tf_files:
        if ".terraform" not in file:
            with open(file, "r") as f:
                content += f"\n\n--- File: {file} ---\n\n{f.read()}"
    return content

def get_cicd_code():
    yaml_files = glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml")
    content = ""
    for file in yaml_files:
        with open(file, "r") as f:
            content += f"\n\n--- Workflow: {file} ---\n\n{f.read()}"
    return content

# ==========================================
# 4. Agenti
# ==========================================
def run_agent(agent_name, system_prompt, input_text, filename, title, current_state, state_key):
    current_hash = get_hash(input_text)
    if current_state.get(state_key) == current_hash:
        print(f"[{agent_name}] Nessuna modifica rilevata al contesto. Salto l'aggiornamento.")
        return current_state
    
    print(f"[{agent_name}] Modifiche rilevate. Generazione documentazione in corso...")
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analizza questo contenuto:\n\n{input_text}"}
        ]
    )
    
    content = response.choices[0].message.content
    final_markdown = get_header(title) + content
    
    # Crea la sottocartella specifica (es. docs/test o docs/prod)
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    with open(f"{DOCS_DIR}/{filename}", "w") as f:
        f.write(final_markdown)
        
    print(f"-> {DOCS_DIR}/{filename} generato con successo.")
    
    current_state[state_key] = current_hash
    return current_state

# ==========================================
# 5. Esecuzione
# ==========================================
if __name__ == "__main__":
    state = load_state()
    
    # Agente 1: Struttura
    prompt_struttura = "Sei un DevOps Architect. Spiega in un documento Markdown la struttura logica e l'organizzazione delle directory di questo progetto. Non parlare di CI/CD qui."
    state = run_agent("Agente 1 (Struttura)", prompt_struttura, get_project_structure(), "struttura_logica.md", "Struttura Logica del Progetto", state, "hash_struttura")
    
    # Agente 2: Moduli Terraform
    prompt_moduli = "Sei un Cloud Engineer. Analizza il codice Terraform fornito. Scrivi un documento Markdown operativo spiegando per ogni modulo il ruolo di business, le risorse create, e le variabili chiave (senza incollare il codice)."
    state = run_agent("Agente 2 (Moduli TF)", prompt_moduli, get_terraform_code(), "ruolo_moduli.md", "Ruolo dei Moduli Terraform", state, "hash_moduli")
    
    # Agente 3: Pipeline CI/CD
    prompt_cicd = "Sei un esperto di automazione. Analizza questi workflow GitHub Actions. Spiega in Markdown l'impostazione del flusso CI/CD, la divisione degli ambienti (es. branch main e test), quali eventi (push) scatenano le action e in che modo queste eseguono il deploy tramite Terraform."
    state = run_agent("Agente 3 (CI/CD)", prompt_cicd, get_cicd_code(), "flusso_cicd.md", "Impostazione Flusso CI/CD", state, "hash_cicd")
    
    save_state(state)
    print("Elaborazione completata!")