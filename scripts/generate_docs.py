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
env = os.getenv("ENVIRONMENT", "sconosciuto")

# DEFINIAMO I DUE MODELLI
MODEL_MINI = "openai/gpt-4o-mini"
MODEL_PRO = "openai/gpt-4o"

STATE_FILE = f".docs_state_{env}.json"
DOCS_DIR = f"docs/{env}"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# ==========================================
# 2. Funzioni di Supporto (Stato e Data)
# ==========================================
def get_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_header(titolo):
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

def get_infra_and_functions_code():
    """Raccoglie il codice Terraform e il codice delle Cloud Functions."""
    # Trova sia i file Terraform che i file Python
    tf_files = glob.glob("**/*.tf", recursive=True)
    py_files = glob.glob("**/*.py", recursive=True)
    
    all_files = tf_files + py_files
    content = ""
    
    for file in all_files:
        # Escludiamo le cartelle di sistema e i nostri script di automazione
        if ".terraform" not in file and "scripts/" not in file and "__pycache__" not in file:
            try:
                with open(file, "r") as f:
                    content += f"\n\n--- File: {file} ---\n\n{f.read()}"
            except Exception as e:
                print(f"Errore nella lettura del file {file}: {e}")
                
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
# AGGIUNTO IL PARAMETRO 'model_to_use' ALLA FUNZIONE
def run_agent(agent_name, system_prompt, input_text, filename, title, current_state, state_key, model_to_use):
    current_hash = get_hash(input_text)
    if current_state.get(state_key) == current_hash:
        print(f"[{agent_name}] Nessuna modifica rilevata al contesto. Salto l'aggiornamento.")
        return current_state
    
    print(f"[{agent_name}] Modifiche rilevate. Generazione documentazione in corso con il modello {model_to_use}...")
    
    response = client.chat.completions.create(
        model=model_to_use, # USA IL MODELLO PASSATO COME PARAMETRO
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analizza questo contenuto:\n\n{input_text}"}
        ]
    )
    
    content = response.choices[0].message.content
    final_markdown = get_header(title) + content
    
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    with open(f"{DOCS_DIR}/{filename}", "w") as f:
        f.write(final_markdown)
        
    print(f"-> {DOCS_DIR}/{filename} generato con successo.")
    
    current_state[state_key] = current_hash
    return current_state

if __name__ == "__main__":
        state = load_state()
        
        # Agente 1: Struttura (Usa 4o-mini)
        prompt_struttura = """Sei un Lead DevOps Architect. Spiega in un documento Markdown la struttura logica e l'organizzazione delle directory di questo progetto. 
        REGOLE FONDAMENTALI: 
        1. Usa un tono tecnico, assertivo, deciso e autorevole. 
        2. NON usare MAI termini dubbiosi come 'probabilmente', 'presumibilmente', 'sembra che', 'potrebbe'. Descrivi a cosa serve un file deducendolo dal nome con assoluta certezza.
        3. Non parlare di CI/CD qui."""
        state = run_agent("Agente 1 (Struttura)", prompt_struttura, get_project_structure(), "struttura_logica.md", "Struttura Logica del Progetto", state, "hash_struttura", MODEL_MINI)
        
        # Agente 2: Moduli Terraform e Cloud Functions (Usa 4o)
        prompt_moduli = """Sei un Senior Cloud Engineer. Analizza il codice Terraform e il codice Python (Cloud Functions) fornito. Scrivi un documento Markdown operativo.
        REGOLE FONDAMENTALI:
        1. Usa un tono tecnico, assertivo e definitivo. Niente supposizioni.
        2. Spiega per ogni modulo Terraform il ruolo di business e le risorse create. 
        3. Spiega per ogni Cloud Function la logica applicativa.
        4. Non incollare mai il codice sorgente nel documento finale."""
        state = run_agent("Agente 2 (Moduli e Funzioni)", prompt_moduli, get_infra_and_functions_code(), "ruolo_moduli.md", "Ruolo dei Moduli e Logica Funzioni", state, "hash_moduli", MODEL_PRO)
        
        # Agente 3: Pipeline CI/CD (Usa 4o-mini)
        prompt_cicd = """Sei un esperto di automazione DevOps. Analizza questi workflow GitHub Actions. Spiega in Markdown l'impostazione del flusso CI/CD, la divisione degli ambienti, gli eventi di trigger e il deploy.
        REGOLE FONDAMENTALI:
        1. Sii diretto e preciso. Non usare termini come 'probabilmente' o 'forse'. 
        2. Elenca in modo chiaro come le action eseguono il deploy tramite Terraform."""
        state = run_agent("Agente 3 (CI/CD)", prompt_cicd, get_cicd_code(), "flusso_cicd.md", "Impostazione Flusso CI/CD", state, "hash_cicd", MODEL_MINI)
        
        save_state(state)
        print("Elaborazione completata!")