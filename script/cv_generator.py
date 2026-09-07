"""
CV Generator - FIXED VERSION WITH BASE64 LOGO EMBEDDING
Ensures logo displays correctly in both HTML and PDF outputs
"""

import os
import json
import logging
import base64
import subprocess
import sys
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import yaml
from tqdm import tqdm
from playwright.sync_api import sync_playwright

# ================================
# CONFIG & PATHS
# ================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
PROMPTS_DIR = PROJECT_ROOT / "config" / "prompts"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# API Configuration
API_CONFIG = CONFIG.get("api", {})

# Load .env file for API key
ENV_PATH = PROJECT_ROOT / "config" / ".env"
if ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=ENV_PATH)
    except ImportError:
        # Manual .env loading if python-dotenv not available
        with open(ENV_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Action 227: data folders resolve under DATA_ROOT via the shared resolver.
# (templates stays under the project root — it is code, not pipeline data.)
try:
    from script.storage_paths import CURRENT_DIR, ARCHIVE_DIR, resolve_session_cv_dir
except ImportError:
    from storage_paths import CURRENT_DIR, ARCHIVE_DIR, resolve_session_cv_dir

INPUT_DIR = CURRENT_DIR / "intermediary_structured"
LOG_DIR = CURRENT_DIR / "logs"
FINAL_RESULT_DIR = CURRENT_DIR / "final_result"
FORMATTED_CV_DIR = CURRENT_DIR / "formatted_cv"
OFFER_DIR = CURRENT_DIR / "offer"
TEMPLATE_DIR = PROJECT_ROOT / CONFIG["paths"]["templates"]

# Fix: Based on your 'ls' output, the logo is in the templates folder
LOGO_PATH = TEMPLATE_DIR / "logo.png"

# ================================
# PLAYWRIGHT BROWSER CHECK
# ================================
PLAYWRIGHT_READY = False

def check_playwright_browsers() -> bool:
    """Check if Playwright browsers are installed."""
    global PLAYWRIGHT_READY
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        PLAYWRIGHT_READY = True
        return True
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            return False
        # Other error, but might still work
        PLAYWRIGHT_READY = True
        return True

def install_playwright_browsers() -> bool:
    """Attempt to install Playwright browsers."""
    print("\n🔧 Installing Playwright browsers (chromium)...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("   ✅ Playwright chromium installed successfully")
            return True
        else:
            print(f"   ❌ Installation failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Installation failed: {e}")
        return False

# Project Optimizer
PROJECT_OPTIMIZER_AVAILABLE = False
EXPERIENCE_OPTIMIZER_AVAILABLE = False
try:
    from cv_optimizer import optimize_projects_with_ai, optimize_experiences_with_ai
    PROJECT_OPTIMIZER_AVAILABLE = True
    EXPERIENCE_OPTIMIZER_AVAILABLE = True
except:
    try:
        from cv_optimizer import optimize_projects_with_ai
        PROJECT_OPTIMIZER_AVAILABLE = True
    except:
        pass

# ================================
# LOGO UTILITIES - NEW!
# ================================
def get_logo_base64(logo_path: Path) -> str:
    """
    Convert logo to base64 data URI for reliable embedding in HTML/PDF.
    This ensures the logo displays correctly in both HTML preview and PDF output.
    """
    if not logo_path.exists():
        return ""
    
    try:
        with open(logo_path, 'rb') as f:
            logo_bytes = f.read()
        
        # Encode to base64
        logo_base64 = base64.b64encode(logo_bytes).decode('utf-8')
        
        # Determine MIME type based on file extension
        ext = logo_path.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/png')
        
        # Return data URI
        return f"data:{mime_type};base64,{logo_base64}"
    except Exception as e:
        logging.error(f"Failed to encode logo: {e}")
        return ""

# ================================
# LOGGING (Update: Session-specific logs)
# ================================
def setup_logging(session_id: str = None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Logic: If a session_id is provided, create a subfolder for logs
    if session_id:
        current_log_dir = LOG_DIR / session_id
    else:
        current_log_dir = LOG_DIR
        
    current_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = current_log_dir / f"cv_generation_{timestamp}.log"
    
    logger = logging.getLogger(f"CVGenerator_{session_id}" if session_id else "CVGenerator")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if the function is called multiple times
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        
        logger.addHandler(fh)
        logger.addHandler(ch)
    
    return logger

# Initial logger - will be replaced when session is known
logger = logging.getLogger("CVGenerator")
logger.setLevel(logging.DEBUG)

# ================================
# UTILITIES
# ================================
def clean_json_content(raw_content: str) -> str:
    if '```' in raw_content:
        parts = raw_content.split('```')
        for part in parts:
            part = part.strip()
            if part.startswith('json'):
                part = part[4:].strip()
            if part.startswith('{'):
                return part
    return raw_content

def validate_cv_json(data: dict) -> Tuple[bool, List[str]]:
    errors = []
    if 'informations_personnelles' not in data:
        errors.append("Missing 'informations_personnelles'")
    else:
        if not data['informations_personnelles'].get('nom_complet'):
            errors.append("Missing 'nom_complet'")
    return len(errors) == 0, errors

def build_cv_index(input_dir: Path) -> Dict[str, Path]:
    logger.info("📇 Construction de l'index des CVs...")
    index = {}
    if not input_dir.exists():
        return index
    for session_dir in input_dir.iterdir():
        if not session_dir.is_dir():
            continue
        for json_file in session_dir.glob("*.json"):
            try:
                raw = json_file.read_text(encoding='utf-8')
                data = json.loads(clean_json_content(raw))
                name = data.get('informations_personnelles', {}).get('nom_complet', '')
                if name:
                    index[name.lower()] = json_file
            except:
                pass
    logger.info(f"✅ {len(index)} CVs indexés")
    return index

def build_cv_index_for_session(cv_source_dir: Path) -> Dict[str, Path]:
    """Build CV index for a specific session directory (with archive fallback support)."""
    logger.info(f"📇 Construction de l'index des CVs pour {cv_source_dir.name}...")
    logger.info(f"   Répertoire source: {cv_source_dir}")
    logger.info(f"   Existe: {cv_source_dir.exists()}")
    
    index = {}
    if not cv_source_dir.exists():
        logger.warning(f"⚠️ Répertoire source introuvable: {cv_source_dir}")
        return index
    
    # List all files in the directory for debugging
    try:
        all_files = list(cv_source_dir.iterdir())
        logger.info(f"   Fichiers trouvés dans le répertoire: {len(all_files)}")
        for f in all_files:
            logger.debug(f"      - {f.name} ({'dir' if f.is_dir() else 'file'})")
    except Exception as e:
        logger.error(f"   Erreur lors de la lecture du répertoire: {e}")
    
    # Index JSON files directly in the source directory
    try:
        json_files = list(cv_source_dir.glob("*.json"))
        logger.info(f"   Fichiers JSON trouvés: {len(json_files)}")
        
        for json_file in json_files:
            try:
                logger.debug(f"   Indexation de: {json_file.name}")
                raw = json_file.read_text(encoding='utf-8')
                data = json.loads(clean_json_content(raw))
                name = data.get('informations_personnelles', {}).get('nom_complet', '')
                if name:
                    index[name.lower()] = json_file
                    logger.debug(f"      ✓ Indexé: {name}")
                else:
                    logger.debug(f"      ⚠️ Pas de nom trouvé dans {json_file.name}")
            except Exception as e:
                logger.debug(f"      ⚠️ Erreur lors de l'indexation de {json_file.name}: {e}")
    except Exception as e:
        logger.error(f"   Erreur lors de la recherche de fichiers JSON: {e}")
    
    logger.info(f"✅ {len(index)} CVs indexés")
    return index

def load_job_offer(session_id: str) -> Optional[str]:
    offer_dir = OFFER_DIR / session_id
    if not offer_dir.exists():
        # Check archive fallback
        archive_offer_dir = ARCHIVE_DIR / session_id / "offer"
        if archive_offer_dir.exists():
            offer_dir = archive_offer_dir
        else:
            return None
    txt_files = list(offer_dir.glob("*.txt"))
    if not txt_files:
        return None
    try:
        with open(txt_files[0], 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return None


# ================================
# JOB TITLE EXTRACTION (AI-POWERED)
# ================================
def load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def call_llm_for_job_title(prompt: str) -> Optional[str]:
    """
    Call the LLM API to extract job title.
    Uses the model configured in config_yaml.yaml.
    """
    import time
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logging.warning("API key not found, falling back to regex extraction")
        return None

    url = f"{API_CONFIG.get('base_url', 'https://openrouter.ai/api/v1')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": API_CONFIG.get("model", "meta-llama/llama-3.1-405b-instruct:free"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": API_CONFIG.get("job_title", {}).get("temperature", 0.0),
        "max_tokens": API_CONFIG.get("job_title", {}).get("max_tokens", 100),
    }

    max_retries = API_CONFIG.get("max_retries", 2)
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=API_CONFIG.get("timeout_seconds", 30))
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return content if content else None
        except requests.exceptions.HTTPError as e:
            if response.status_code in [502, 503, 504] and attempt < max_retries - 1:
                time.sleep(2)  # Brief wait before retry
                continue
            logging.warning(f"LLM API call failed: {e}")
            return None
        except Exception as e:
            logging.warning(f"LLM API call failed: {e}")
            return None
    
    return None


def extract_job_title_with_ai(offer_content: str) -> Optional[str]:
    """
    Extract job title using AI/LLM for more precise results.
    """
    try:
        prompt_template = load_prompt("job_title_extraction_prompt.txt")
        prompt = prompt_template.format(offer_content=offer_content[:2000])  # Limit content size
        
        job_title = call_llm_for_job_title(prompt)
        
        if job_title:
            # Clean up any extra formatting from LLM response
            job_title = job_title.strip().strip('"\'').strip()
            # Remove any "Le poste est:" or similar prefixes the LLM might add
            import re
            job_title = re.sub(r'^(le\s+poste\s+(est|recherché)\s*:?\s*)', '', job_title, flags=re.IGNORECASE)
            job_title = re.sub(r'^(titre\s*:?\s*)', '', job_title, flags=re.IGNORECASE)
            return job_title.strip()
        
        return None
    except Exception as e:
        logging.warning(f"AI extraction failed: {e}")
        return None


def extract_job_title_with_regex(offer_content: str) -> Optional[str]:
    """
    Fallback: Extract job title using regex patterns.
    Used when AI extraction is unavailable or fails.
    """
    import re
    
    if not offer_content:
        return None
    
    job_title = None
    
    # Common stop words/phrases that indicate end of job title
    stop_words = r"(?:\s+pour|\s+afin|\s+dans|\s+au\s+sein|\s+chez|\s+à|\s+sur|\s+avec|\s+qui|\s+capable|\s+ayant|\s+possédant|\s+maîtrisant|\s+souhaitant|\s*[,.\n!?]|$)"
    
    # Pattern 1: "Vous êtes un/une [TITLE] et souhaitez/qui souhaitez"
    pattern1 = r"[Vv]ous\s+[êe]tes\s+(?:un|une)\s+([^,\n]+?)(?:\s+et\s+souhaitez|\s+qui\s+souhaitez|\s*\?)"
    
    # Pattern 2: "Nous recherchons/sommes à la recherche d'un/une [TITLE]"
    # Handle both "d'un" (apostrophe) and "d un" (space) formats
    pattern2 = r"(?:[Nn]ous\s+recherchons\s+(?:un|une)\s+|[Nn]ous\s+sommes\s+[àa]\s+la\s+recherche\s+d(?:[''\s])\s*(?:un\s+|une\s+)?)([A-Za-zÀ-ÿ\s\-/\.\+]+?)" + stop_words
    
    # Pattern 3: "Recrutement de/d' [TITLE]"
    pattern3 = r"[Rr]ecrutement\s+d(?:e\s+|[''])\s*([A-Za-zÀ-ÿ\s\-/\+]+?)" + stop_words
    
    # Pattern 4: "Poste/Profil/Offre: [TITLE]"
    pattern4 = r"(?:[Pp]oste|[Pp]rofil|[Oo]ffre|[Ii]ntitul[ée]\s+du\s+poste)\s*:\s*([A-Za-zÀ-ÿ\s\-/\+]+?)(?:\s*[\n,]|$)"
    
    # Pattern 5: "pour [NUMBER]+ [TITLE]"
    pattern5 = r"pour\s+(?:plus\s+de\s+)?\d+\s+([A-Za-zÀ-ÿ\s\-/\+]+?)(?:\s*,|\s*afin|\s*pour|\s*\n)"
    
    # Pattern 6: "en tant que [TITLE]"
    pattern6 = r"en\s+tant\s+que\s+([A-Za-zÀ-ÿ\s\-/\.\+]+?)(?:\s+H/?F|\s+pour|\s+au|\s+chez|\s*[,.\n]|$)"
    
    # Pattern 7: Direct title at start (e.g., "Consultant SAP FI/CO Senior - Mission")
    pattern7 = r"^([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ\-/]+){1,5}(?:\s+(?:Senior|Junior|Expert|Lead|Manager|Confirmé|Expérimenté))?)\s*[\-–—]"
    
    patterns = [pattern1, pattern2, pattern3, pattern4, pattern5, pattern6, pattern7]
    
    for pattern in patterns:
        match = re.search(pattern, offer_content, re.IGNORECASE | re.MULTILINE)
        if match:
            job_title = match.group(1).strip()
            break
    
    if job_title:
        job_title = normalize_job_title(job_title)
    
    return job_title


def extract_job_title_from_offer(offer_content: Optional[str], use_ai: bool = True) -> Optional[str]:
    """
    Extract and normalize the job title from a job offer text.
    
    Args:
        offer_content: The job offer text
        use_ai: If True, try AI extraction first (default: True)
    
    Returns:
        Normalized job title or None if not found
    """
    if not offer_content:
        return None
    
    job_title = None
    
    # Try AI extraction first if enabled
    if use_ai:
        job_title = extract_job_title_with_ai(offer_content)
        if job_title:
            logging.info(f"✅ Job title extracted via AI: {job_title}")
            return job_title
    
    # Fallback to regex extraction
    job_title = extract_job_title_with_regex(offer_content)
    if job_title:
        logging.info(f"✅ Job title extracted via regex: {job_title}")
    
    return job_title
    
    return job_title


def normalize_job_title(title: str) -> str:
    """
    Clean and normalize the extracted job title.
    
    - Removes excessive whitespace
    - Capitalizes properly
    - Removes trailing punctuation
    - Standardizes common terms
    """
    import re
    
    if not title:
        return ""
    
    # Remove leading/trailing whitespace and punctuation
    title = title.strip().rstrip('.,;:!?')
    
    # Remove "un/une" prefix that might be captured
    title = re.sub(r'^(?:un|une)\s+', '', title, flags=re.IGNORECASE)
    
    # Remove emojis and special characters at the start
    title = re.sub(r'^[👉🎯✅◾\-•\s]+', '', title)
    
    # Normalize whitespace
    title = re.sub(r'\s+', ' ', title)
    
    # Remove "senior" duplication and clean up
    title = re.sub(r'\s+senior\s+senior', ' Senior', title, flags=re.IGNORECASE)
    
    # Capitalize each word intelligently
    title_words = title.split()
    capitalized = []
    
    # Words that should stay lowercase (unless first word)
    lowercase_words = {'de', 'du', 'des', 'le', 'la', 'les', 'et', 'en', 'à', 'au', 'aux'}
    
    # Words/acronyms that should be uppercase but with special casing
    special_casing = {
        'devops': 'DevOps',
        'ios': 'iOS',
        'api': 'API',
        'ui': 'UI',
        'ux': 'UX',
        'sql': 'SQL',
        'js': 'JS',
        'ts': 'TS',
        'ci': 'CI',
        'cd': 'CD',
        'it': 'IT',
        'qa': 'QA',
        'bi': 'BI',
        'ml': 'ML',
        'ai': 'AI',
        'sap': 'SAP',
        'erp': 'ERP',
        'crm': 'CRM',
        'aws': 'AWS',
        'gcp': 'GCP',
        'node.js': 'Node.js',
        'node': 'Node',
        'react.js': 'React.js',
        'react': 'React',
        'vue.js': 'Vue.js',
        'vue': 'Vue',
        'angular.js': 'Angular.js',
        'angular': 'Angular',
        'fi/co': 'FI/CO',
        'sd': 'SD',
        'mm': 'MM',
        'abap': 'ABAP',
    }
    
    for i, word in enumerate(title_words):
        word_lower = word.lower()
        
        if word_lower in special_casing:
            capitalized.append(special_casing[word_lower])
        elif i == 0 or word_lower not in lowercase_words:
            capitalized.append(word.capitalize())
        else:
            capitalized.append(word_lower)
    
    result = ' '.join(capitalized)
    
    # Common replacements for cleaner titles
    replacements = {
        'Full Stack': 'Full Stack',
        'Fullstack': 'Full Stack',
        'full stack': 'Full Stack',
        'Back End': 'Back-End',
        'Back-end': 'Back-End',
        'Front End': 'Front-End',
        'Front-end': 'Front-End',
    }
    
    for old, new in replacements.items():
        result = re.sub(re.escape(old), new, result, flags=re.IGNORECASE)
    
    # Fix specific framework formats (e.g., React/node.js -> React/Node.js)
    result = re.sub(r'([Rr]eact|[Vv]ue|[Aa]ngular)/[Nn]ode\.?[Jj]?[Ss]?', r'\1/Node.js', result)
    result = re.sub(r'/[Nn]ode$', '/Node.js', result)  # Handle trailing /node
    
    return result

def html_escape(text: str) -> str:
    if not text: return ""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

# ================================
# SECTION GENERATORS
# ================================
def generate_formation_section(data: Dict[str, Any]) -> str:
    formations = data.get("formation", [])
    if not formations: return ""
    items = []
    for f in formations:
        inst = html_escape(f.get("institution", ""))
        lieu = html_escape(f.get("lieu", ""))
        dates = html_escape(f.get("dates", ""))
        diplome = html_escape(f.get("diplome", ""))
        details = html_escape(f.get("details", ""))
        html = f'<div style="margin-bottom:0.4cm"><b>{inst}'
        if lieu: html += f', {lieu}'
        html += '</b><br>'
        if dates: html += f'<i style="color:#666;font-size:9pt">{dates}</i><br>'
        html += f'<div style="padding-left:0.3cm;border-left:2px solid #3498db;margin-top:0.1cm">{diplome}'
        if details: html += f'<br><span style="font-size:9pt;color:#555">{details}</span>'
        html += '</div></div>'
        items.append(html)
    return f'<h1>Formation</h1>{"".join(items)}'

def generate_certifications_section(data: Dict[str, Any]) -> str:
    certs = data.get("certifications", [])
    if not certs: return ""
    items = []
    for cert in certs:
        nom = html_escape(cert.get("nom", ""))
        organisme = html_escape(cert.get("organisme", ""))
        date = html_escape(cert.get("date", ""))
        text = f"{nom}"
        if organisme: text += f", {organisme}"
        if date: text += f" ({date})"
        items.append(f'<li style="margin-bottom:0.15cm;padding-left:0.4cm;position:relative">'
                    f'<span style="position:absolute;left:0;color:#3498db;font-weight:bold">•</span>{text}</li>')
    return f'<h1>Certifications</h1><ul style="list-style:none;padding:0">{"".join(items)}</ul>'

def generate_competences_section(data: Dict[str, Any]) -> str:
    comp = data.get("competences", {})
    if not comp: return ""
    sections = []
    if isinstance(comp, dict):
        for key, value in comp.items():
            if isinstance(value, list) and value:
                title = html_escape(key.replace("_", " ").title())
                skills = " • ".join(html_escape(str(s)) for s in value if s)
                sections.append(f'<div style="margin-bottom:0.3cm"><b style="color:#2c3e50;font-size:10pt">{title}:</b><br>'
                              f'<div style="font-size:9.5pt;line-height:1.3">{skills}</div></div>')
    return f'<h1>Compétences</h1>{"".join(sections)}'

def generate_langues_section(data: Dict[str, Any]) -> str:
    langues = data.get("langues", [])
    if not langues: return ""
    items = []
    for lang in langues:
        # Support both "nom" (from extraction) and "langue" (legacy) keys
        langue = html_escape(lang.get("nom", "") or lang.get("langue", "") or lang.get("name", ""))
        niveau = html_escape(lang.get("niveau", "") or lang.get("level", ""))
        if langue:  # Only add if language name exists
            items.append(f'<div style="margin-bottom:0.15cm;font-size:9.5pt"><b>{langue}:</b> {niveau}</div>')
    return f'<h1>Langues</h1>{"".join(items)}' if items else ""

def generate_projets_section(data: Dict[str, Any]) -> str:
    projets = data.get("projets_realises", [])
    if not projets: return ""
    items = []
    for proj in projets:
        nom = html_escape(proj.get("nom", ""))
        description = html_escape(proj.get("description", ""))
        technologies = proj.get("technologies", [])
        html = f'<div style="margin-bottom:0.3cm">'
        html += f'<div style="font-weight:bold;font-size:10pt;color:#2c3e50">• {nom}</div>'
        if description: html += f'<div style="font-size:9.5pt;margin-top:0.05cm;line-height:1.25">{description}</div>'
        if technologies:
            tech_text = ", ".join(html_escape(str(t)) for t in technologies if t)
            html += f'<div style="font-size:8.5pt;color:#666;margin-top:0.05cm"><i>Tech: {tech_text}</i></div>'
        html += '</div>'
        items.append(html)
    return f'<h1>Projets Réalisés</h1>{"".join(items)}'


def generate_profile_section(data: Dict[str, Any], job_offer_content: Optional[str] = None) -> str:
    """
    Generate the profile presentation section.
    Uses AI to create a dynamic, job-aligned profile description.
    Falls back to static description if AI is unavailable.
    """
    # Try AI-powered generation first
    ai_description = generate_profile_with_ai(data, job_offer_content)
    
    if ai_description:
        description = html_escape(ai_description)
    else:
        # Fallback to static profile from CV
        profil = data.get("profil_resume", {})
        if not profil:
            return ""
        description = html_escape(profil.get("description", ""))
        if not description:
            return ""
    
    # Build the profile section HTML
    html = '<div style="margin-bottom:0.4cm;padding:0.3cm;background:#f8f9fa;border-left:4px solid #3498db;border-radius:0 4px 4px 0">'
    html += '<h1 style="margin-top:0;margin-bottom:0.2cm">Profil</h1>'
    html += f'<div style="font-size:10pt;line-height:1.4;color:#2c3e50;text-align:justify">{description}</div>'
    html += '</div>'
    
    return html


def generate_profile_with_ai(data: Dict[str, Any], job_offer_content: Optional[str] = None) -> Optional[str]:
    """
    Generate a dynamic profile description using AI.
    The profile is tailored to highlight skills relevant to the job offer.
    """
    import time
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logging.debug("API key not found, using static profile")
        return None
    
    try:
        # Extract candidate info
        info = data.get("informations_personnelles", {})
        profil = data.get("profil_resume", {})
        competences = data.get("competences", {})
        experiences = data.get("experiences_professionnelles", [])
        
        candidate_name = info.get("nom_complet", "Candidat")
        current_title = info.get("titre", "")
        years_exp = profil.get("annees_experience", "")
        specializations = profil.get("specialisations", [])
        
        # Build key skills summary
        key_skills = []
        if isinstance(competences, dict):
            for category, skills in competences.items():
                if isinstance(skills, list) and skills:
                    key_skills.extend(skills[:5])  # Top 5 from each category
        key_skills_text = ", ".join(key_skills[:15]) if key_skills else "Non spécifié"
        
        # Build recent experiences summary
        recent_exp_text = ""
        for exp in experiences[:2]:  # Last 2 experiences
            titre = exp.get("titre_poste", "")
            entreprise = exp.get("entreprise", "")
            if titre:
                recent_exp_text += f"- {titre} chez {entreprise}\n"
        
        # Load prompt template
        prompt_template = load_prompt("profile_generation_prompt.txt")
        
        prompt = prompt_template.format(
            candidate_name=candidate_name,
            current_title=current_title,
            years_experience=years_exp or "Non spécifié",
            specializations=", ".join(specializations) if specializations else "Non spécifié",
            key_skills=key_skills_text,
            recent_experiences=recent_exp_text or "Non spécifié",
            job_offer=job_offer_content[:1500] if job_offer_content else "Non spécifié"
        )
        
        # Call LLM API
        url = f"{API_CONFIG.get('base_url', 'https://openrouter.ai/api/v1')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": API_CONFIG.get("model", "meta-llama/llama-3.1-405b-instruct:free"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": API_CONFIG.get("profile_gen", {}).get("temperature", 0.3),
            "max_tokens": API_CONFIG.get("profile_gen", {}).get("max_tokens", 200),
        }

        max_retries = API_CONFIG.get("max_retries", 2)
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=API_CONFIG.get("timeout_seconds", 30))
                response.raise_for_status()
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                if content:
                    # Clean up any markdown or extra formatting
                    content = content.strip().strip('"\'').strip()
                    logging.info(f"✅ Profile generated via AI for {candidate_name}")
                    return content
                    
            except requests.exceptions.HTTPError as e:
                if response.status_code in [502, 503, 504] and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                logging.warning(f"LLM API error for profile generation: {e}")
                return None
            except Exception as e:
                logging.warning(f"Profile generation API call failed: {e}")
                return None
        
        return None
        
    except Exception as e:
        logging.warning(f"AI profile generation failed: {e}")
        return None


def generate_experiences_section(data: Dict[str, Any]) -> str:
    exps = data.get("experiences_professionnelles", [])
    if not exps: return ""
    items = []
    for exp in exps:
        titre = html_escape(exp.get("titre_poste", ""))
        entreprise = html_escape(exp.get("entreprise", ""))
        lieu = html_escape(exp.get("lieu", ""))
        dates = html_escape(exp.get("dates", ""))
        contexte = html_escape(exp.get("contexte", ""))
        missions = exp.get("missions", [])
        environnement = exp.get("environnement", [])
        company = entreprise + (f", {lieu}" if lieu else "")
        html = f'<div style="margin-bottom:0.5cm;page-break-inside:avoid">'
        html += f'<div style="font-size:11pt;font-weight:bold;color:#2c3e50;margin-bottom:0.1cm">{titre}</div>'
        html += f'<div style="display:flex;justify-content:space-between;font-size:10pt;margin-bottom:0.1cm">'
        html += f'<b style="color:#3498db">{company}</b><i style="color:#7f8c8d;font-size:9pt">{dates}</i></div>'
        if contexte: html += f'<div style="font-size:9.5pt;font-style:italic;color:#555;margin-bottom:0.2cm">{contexte}</div>'
        if missions:
            html += '<ul style="list-style:none;padding-left:0.4cm;margin-bottom:0.15cm">'
            for mission in missions:
                html += f'<li style="margin-bottom:0.1cm;position:relative;font-size:9.5pt">'
                html += f'<span style="position:absolute;left:-0.4cm;color:#3498db;font-weight:bold">▸</span>{html_escape(mission)}</li>'
            html += '</ul>'
        if environnement:
            env_text = ", ".join(html_escape(str(e)) for e in environnement if e)
            html += f'<div style="font-size:9pt;color:#555;background:#f9f9f9;padding:0.15cm;border-left:3px solid #3498db;margin-top:0.2cm">'
            html += f'<b>Environnement :</b> {env_text}</div>'
        html += '</div>'
        items.append(html)
    return f'<h1>Expériences Professionnelles</h1>{"".join(items)}'

def generate_html_from_json(json_data: Dict[str, Any], template_name: str = "classic", job_title: Optional[str] = None, job_offer_content: Optional[str] = None) -> str:
    template_path = TEMPLATE_DIR / f"{template_name}.html"
    if not template_path.exists():
        template_path = TEMPLATE_DIR / "classic.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    info = json_data.get("informations_personnelles", {})
    nom_complet = html_escape(info.get("nom_complet", "CV"))
    
    # Use job title from offer if provided, otherwise fall back to CV's original title
    if job_title:
        titre = html_escape(job_title)
    else:
        titre = html_escape(info.get("titre", ""))
    
    # FIX: Use base64 encoding instead of file URI for reliable PDF generation
    logo_url = get_logo_base64(LOGO_PATH)
    
    # For minimal template, reorder sections so profile comes before formation
    if template_name == "minimal":
        left_content = "".join([
            generate_profile_section(json_data, job_offer_content),
            generate_formation_section(json_data),
            generate_certifications_section(json_data),
            generate_competences_section(json_data),
            generate_langues_section(json_data)
        ])
        
        right_content_page1 = "".join([
            generate_experiences_section(json_data),
            generate_projets_section(json_data)
        ])
    else:
        left_content = "".join([
            generate_formation_section(json_data),
            generate_certifications_section(json_data),
            generate_competences_section(json_data),
            generate_langues_section(json_data)
        ])
        
        right_content_page1 = "".join([
            generate_profile_section(json_data, job_offer_content),
            generate_experiences_section(json_data),
            generate_projets_section(json_data)
        ])
    
    return template.format(
        nom_complet=nom_complet,
        titre=titre,
        left_content=left_content,
        right_content_page1=right_content_page1,
        logo_url=logo_url,
        additional_pages=""
    )

def generate_pdf_from_html(html_content: str, output_path: Path, logger_instance=None, retries: int = 2) -> Tuple[bool, str]:
    """
    Generate PDF from HTML content using Playwright with retry logic.
    
    Args:
        html_content: HTML content to convert
        output_path: Path where PDF should be saved
        logger_instance: Logger instance
        retries: Number of retry attempts
    
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    log = logger_instance or logger
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            log.debug(f"   PDF generation attempt {attempt + 1}/{retries + 1}...")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                    ]
                )
                page = browser.new_page()
                _pdf_timeout = CONFIG.get("cv_generation", {}).get("pdf", {}).get("timeout_ms", 60000)
                page.set_default_timeout(_pdf_timeout)
                page.set_content(html_content, wait_until="domcontentloaded", timeout=_pdf_timeout)
                page.pdf(
                    path=str(output_path),
                    format='A4',
                    print_background=True
                )
                browser.close()
            
            log.debug(f"   ✅ PDF generated successfully: {output_path.name}")
            return True, ""
            
        except Exception as e:
            last_error = str(e)
            
            # Check for known issues
            if "Executable doesn't exist" in last_error or "browserType.launch" in last_error:
                log.error("❌ Playwright browsers not installed!")
                log.error("   Run: playwright install chromium")
                return False, "Playwright browsers not installed"
            
            elif "No protocol" in last_error or "port" in last_error:
                log.warning(f"   ⚠️  Attempt {attempt + 1} failed (connection issue): retrying...")
                if attempt < retries:
                    import time
                    time.sleep(2)  # Wait longer before retry
                    continue
            
            # Other errors - log and retry if attempts remain
            log.warning(f"   ⚠️  PDF generation attempt {attempt + 1} failed: {last_error}")
            if attempt < retries:
                import time
                time.sleep(2)
                continue
            
            return False, last_error
    
    log.error(f"❌ PDF generation failed after {retries + 1} attempts: {last_error}")
    return False, last_error

# ================================
# MAIN PROCESSING
# ================================
# ================================
# SCORE THRESHOLD VALIDATION
# ================================
SCORE_THRESHOLD = CONFIG.get("matching", {}).get("score_threshold", 50.0)

def check_candidates_below_threshold(candidates: List[Dict], threshold: float = SCORE_THRESHOLD) -> List[Dict]:
    """
    Check which candidates have a final score below the threshold.
    
    Args:
        candidates: List of candidate dictionaries with 'final_score'
        threshold: Minimum acceptable score (default 50%)
    
    Returns:
        List of candidates below threshold
    """
    below_threshold = []
    for c in candidates:
        score = c.get('final_score', 0)
        if score < threshold:
            below_threshold.append(c)
    return below_threshold


def display_threshold_warning(below_threshold: List[Dict], threshold: float = SCORE_THRESHOLD) -> None:
    """
    Display a warning about candidates below the score threshold.
    
    Args:
        below_threshold: List of candidates below threshold
        threshold: The threshold value used
    """
    # print("\n" + "⚠️ " * 10)
    print(f"\n⚠️  ATTENTION: {len(below_threshold)} candidat(s) ont un score final inférieur à {int(threshold)}%")
    print("\n" + "-" * 60)
    print(f"   {'Candidat':<30} {'Score Final':>15}")
    print(f"   {'-'*30} {'-'*15}")
    
    for c in below_threshold:
        name = c.get('name', 'Inconnu')[:29]
        score = c.get('final_score', 0)
        score_display = f"{int(round(score))}%"
        print(f"   {name:<30} {score_display:>15}")
    
    print("-" * 60)


def prompt_threshold_confirmation(below_threshold: List[Dict], all_candidates: List[Dict], threshold: float = SCORE_THRESHOLD) -> List[Dict]:
    """
    Prompt user to confirm inclusion of candidates below threshold.
    
    Args:
        below_threshold: List of candidates below threshold
        all_candidates: Complete list of selected candidates
        threshold: The threshold value used
    
    Returns:
        List of candidates to process (filtered or not based on user choice)
    """
    display_threshold_warning(below_threshold, threshold)
    
    above_threshold_count = len(all_candidates) - len(below_threshold)
    
    print(f"\n   Options:")
    print(f"   [Y] Oui - Continuer et formater TOUS les {len(all_candidates)} CV(s) (incluant ceux < {int(threshold)}%)")
    print(f"   [N] Non - Exclure les candidats < {int(threshold)}% et formater uniquement les {above_threshold_count} CV(s) restants")
    print(f"   [C] Annuler - Ne formater aucun CV")
    print()
    
    while True:
        choice = input(f"   → Votre choix (Y/N/C) [N]: ").strip().upper()
        
        if choice == '' or choice == 'N':
            # Exclude candidates below threshold
            filtered = [c for c in all_candidates if c.get('final_score', 0) >= threshold]
            print(f"\n   ✅ {len(below_threshold)} candidat(s) exclu(s). {len(filtered)} CV(s) seront formatés.")
            return filtered
        
        elif choice == 'Y':
            # Include all candidates
            print(f"\n   ✅ Confirmation reçue. TOUS les {len(all_candidates)} CV(s) seront formatés.")
            return all_candidates
        
        elif choice == 'C':
            # Cancel entirely
            print("\n   ❌ Opération annulée. Aucun CV ne sera formaté.")
            return []
        
        else:
            print("   ❌ Choix invalide. Veuillez entrer Y, N ou C.")


def process_from_final_result(session_id: str, limit: Optional[int] = None, template_name: str = "classic", 
                               skip_threshold_check: bool = False, pre_filtered_candidates: Optional[List[Dict]] = None) -> Dict[str, int]:
    # Fix: Setup session-specific logger
    session_logger = setup_logging(session_id)
    session_logger.info(f"🚀 Traitement session: {session_id}")

    # Action 234: intermediary_structured (CV+Offer) → cv_source marker / CV_Theque → archive extracted
    cv_source_dir = resolve_session_cv_dir(session_id)
    session_logger.info(f"📁 Répertoire source CV: {cv_source_dir}")
    if cv_source_dir:
        session_logger.info(f"   Existe: {cv_source_dir.exists()}")
    else:
        session_logger.warning(
            f"⚠️ CVs introuvables — ni intermediary_structured, ni cv_source marker, ni archive extracted"
        )
    
    # Check for intermediary CV files and use archive fallback if needed - FINAL RESULT
    final_result_path = FINAL_RESULT_DIR / session_id / "final_result.json"
    session_logger.info(f"📋 Recherche des résultats finaux en: {final_result_path}")
    session_logger.info(f"   Existe: {final_result_path.exists()}")
    
    if not final_result_path.exists():
        # Check archive fallback for final results
        archive_final_path = ARCHIVE_DIR / session_id / "final" / "final_result.json"
        session_logger.info(f"📋 Répertoire primaire n'existe pas, vérification de l'archive: {archive_final_path}")
        session_logger.info(f"   Existe: {archive_final_path.exists()}")
        
        if archive_final_path.exists():
            session_logger.info(f"📋 Résultats finaux trouvés en archive")
            final_result_path = archive_final_path
        else:
            session_logger.error("❌ Résultats finaux introuvables (ni en primary ni en archive)")
            return {"total": 0, "success": 0, "failed": 0}
    
    with open(final_result_path, 'r') as f:
        final_results = json.load(f)
    
    # Use pre-filtered candidates if provided, otherwise load from file
    if pre_filtered_candidates is not None:
        candidates = pre_filtered_candidates
        session_logger.info(f"📍 Utilisation de {len(candidates)} candidat(s) pré-filtrés")
    else:
        candidates = final_results.get('candidates', [])
        
        # Update: Handle top N logic
        if limit:
            candidates = candidates[:limit]
            session_logger.info(f"📍 Limité au top {limit} candidats")
        
        # Threshold check (only if not skipped and not using pre-filtered)
        if not skip_threshold_check and candidates:
            below_threshold = check_candidates_below_threshold(candidates)
            if below_threshold:
                candidates = prompt_threshold_confirmation(below_threshold, candidates)
                if not candidates:
                    session_logger.info("❌ Opération annulée par l'utilisateur")
                    return {"total": 0, "success": 0, "failed": 0}

    formatted_cv_dir = FORMATTED_CV_DIR / session_id
    formatted_cv_dir.mkdir(parents=True, exist_ok=True)
    cv_index = build_cv_index_for_session(cv_source_dir) if cv_source_dir else {}
    job_offer_content = load_job_offer(session_id)
    
    # Extract job title from offer for CV header
    job_title = extract_job_title_from_offer(job_offer_content)
    if job_title:
        session_logger.info(f"📋 Job title extracted: {job_title}")
    else:
        session_logger.warning("⚠️ Could not extract job title from offer, using CV's original title")
    
    stats = {'total': len(candidates), 'success': 0, 'failed': 0}
    
    for idx, candidate in enumerate(tqdm(candidates, desc=f"Session {session_id}"), 1):
        name = candidate.get("name", "Inconnu")
        json_path = cv_index.get(name.lower())
        
        if not json_path:
            session_logger.error(f"   ❌ CV introuvable pour {name}")
            stats['failed'] += 1
            continue
        
        try:
            json_data = json.loads(clean_json_content(json_path.read_text(encoding='utf-8')))
            
            # Keep original AI optimization logic
            if PROJECT_OPTIMIZER_AVAILABLE and CONFIG.get("project_optimization", {}).get("enabled", False):
                projects = json_data.get("projets_realises", [])
                if projects:
                    json_data["projets_realises"] = optimize_projects_with_ai(projects, job_offer_content, max_projects=CONFIG.get("project_optimization", {}).get("max_projects", 6))
            
            if EXPERIENCE_OPTIMIZER_AVAILABLE and CONFIG.get("experience_optimization", {}).get("enabled", False):
                exps = json_data.get("experiences_professionnelles", [])
                if exps:
                    m = CONFIG.get("experience_optimization", {}).get("max_missions_per_experience", 5)
                    json_data["experiences_professionnelles"] = optimize_experiences_with_ai(exps, job_offer_content, max_missions_per_experience=m)

            html_content = generate_html_from_json(json_data, template_name=template_name, job_title=job_title, job_offer_content=job_offer_content)
            
            base_name = name.replace(' ', '_')
            html_path = formatted_cv_dir / f"{base_name}.html"
            html_path.write_text(html_content, encoding='utf-8')
            session_logger.info(f"   ✅ HTML généré: {base_name}.html")
            
            # Generate PDF - this is now required
            pdf_path = formatted_cv_dir / f"{base_name}.pdf"
            pdf_success, pdf_error = generate_pdf_from_html(html_content, pdf_path, session_logger)
            if pdf_success:
                session_logger.info(f"   ✅ PDF généré: {base_name}.pdf")
            else:
                session_logger.error(f"   ❌ PDF échoué pour {name}: {pdf_error}")
                raise Exception(f"PDF generation failed for {name}: {pdf_error}")
            
            # Count as success only if both HTML and PDF were generated
            stats['success'] += 1
                
        except Exception as e:
            session_logger.exception(f"   ❌ Erreur: {e}")
            stats['failed'] += 1
    
    session_logger.info(f"Fin session {session_id}: {stats['success']}/{stats['total']} réussis")
    return stats

# ================================
# MAIN
# ================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CV Generator - Generate formatted CVs from final results")
    parser.add_argument("--session", type=str, help="Session ID to process (if not specified, processes all sessions)")
    parser.add_argument("--template", type=str, default="classic", help="Template name to use (default: classic)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of CVs to generate per session")
    parser.add_argument("--candidates-file", type=str, default=None, help="Path to a JSON file with an explicit list of candidate names to format (overrides --limit)")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts")
    parser.add_argument("--skip-threshold-check", action="store_true", help="Skip threshold confirmation prompts")
    parser.add_argument("--no-playwright-install", action="store_true", help="Do not prompt to install Playwright browsers")
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("📋 GÉNÉRATEUR DE CV - VERSION FIXÉE (Logo Base64 + PDF)")
    print("="*70)

    # Initialize session-specific logger if session_id is provided
    logger = setup_logging(args.session)

    # Check Playwright browsers
    print("\n🔍 Vérification des navigateurs Playwright...")
    if not check_playwright_browsers():
        print("   ⚠️  Navigateurs Playwright non installés!")
        if not args.non_interactive and not args.no_playwright_install:
            install_choice = input("   Voulez-vous les installer maintenant? (o/n) [o]: ").strip().lower()
            if install_choice != 'n':
                if not install_playwright_browsers():
                    print("\n❌ Impossible d'installer Playwright. PDF ne sera pas généré.")
                    print("   Installez manuellement avec: playwright install chromium")
                else:
                    PLAYWRIGHT_READY = True
        else:
            print("   ⚠️  Mode non-interactif: PDF sera ignoré si Playwright absent.")
    else:
        print("   ✅ Playwright prêt pour la génération PDF")
    
    # Template Selection
    print("\n📄 Templates disponibles:")
    templates = sorted([f.stem for f in TEMPLATE_DIR.glob("*.html")])
    template_name = args.template or "classic"
    limit = args.limit

    # Optional explicit candidate selection (overrides --limit). Max 10 names.
    selected_names = None
    if args.candidates_file:
        try:
            with open(args.candidates_file, "r", encoding="utf-8") as f:
                raw_names = json.load(f)
            if isinstance(raw_names, list):
                selected_names = {str(n).strip() for n in raw_names if str(n).strip()}
                selected_names = set(list(selected_names)[:10])
                print(f"📍 Sélection manuelle: {len(selected_names)} candidat(s) demandé(s)")
        except Exception as e:
            print(f"⚠️  Impossible de lire la sélection de candidats ({args.candidates_file}): {e}")
            selected_names = None
    if templates:
        for i, t in enumerate(templates, 1):
            print(f"  {i}. {t}")
        if not args.non_interactive:
            choice = input(f"\nSélectionnez un template (1-{len(templates)}) [1]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(templates):
                template_name = templates[int(choice)-1]

            print("\n" + "-"*70)
            limit_input = input("Combien de CVs formater par session? (Entrez un nombre ou 'all') [all]: ").strip().lower()
            limit = int(limit_input) if limit_input.isdigit() else None
            print("-"*70)

    # Handle single session vs all sessions
    if args.session:
        # Specific session requested (typically from main.py pipeline)
        session_folder = FINAL_RESULT_DIR / args.session
        final_result_exists = session_folder.exists() and (session_folder / "final_result.json").exists()
        
        # Check archive fallback
        if not final_result_exists:
            archive_session = ARCHIVE_DIR / args.session / "final" / "final_result.json"
            if archive_session.exists():
                print(f"📁 Session trouvée en archive: {args.session}")
                final_result_exists = True
            else:
                print(f"❌ Session introuvable: {args.session}")
                print(f"   Répertoire primaire: {session_folder / 'final_result.json'}")
                print(f"   Archive fallback: {archive_session}")
                exit(1)
        
        session_folders = [session_folder]
        print(f"\n📂 Session spécifique: {args.session}")
    else:
        # Process all sessions - check both primary and archive locations
        session_folders = [d for d in FINAL_RESULT_DIR.iterdir() if d.is_dir() and (d / "final_result.json").exists()]
        
        # Also check for sessions in archive
        archive_base = ARCHIVE_DIR
        if archive_base.exists():
            for archive_session in archive_base.iterdir():
                if archive_session.is_dir() and (archive_session / "final" / "final_result.json").exists():
                    # Create a wrapper object that has the session name
                    # but we'll handle the path resolution in the main loop
                    primary_path = FINAL_RESULT_DIR / archive_session.name
                    if primary_path not in session_folders:
                        # Add a simple object with just a name attribute for sessions only in archive
                        session_folders.append(primary_path)
        
        if not session_folders:
            print("❌ Aucune session trouvée.")
            exit(1)
        
        print(f"\n📂 {len(session_folders)} session(s) à traiter")
    
    # Process each session with threshold checking
    session_stats: Dict[str, int] = {"total": 0, "success": 0, "failed": 0}
    for folder in session_folders:
        print(f"\n{'='*70}")
        print(f"📁 Session: {folder.name}")
        print(f"{'='*70}")
        
        # Load candidates to check scores before processing
        final_result_path = folder / "final_result.json"
        
        # Try archive fallback if primary path doesn't exist
        if not final_result_path.exists():
            archive_path = ARCHIVE_DIR / folder.name / "final" / "final_result.json"
            if archive_path.exists():
                print(f"📋 Utilisation des résultats finaux en archive")
                final_result_path = archive_path
            else:
                print(f"❌ Résultats finaux introuvables pour {folder.name}")
                continue
        
        try:
            with open(final_result_path, 'r', encoding='utf-8') as f:
                final_results = json.load(f)
        except Exception as e:
            print(f"❌ Erreur lors de la lecture des résultats finaux: {e}")
            continue
        
        candidates = final_results.get('candidates', [])
        
        # Apply an explicit manual selection first (overrides limit), else top-N limit.
        if selected_names:
            candidates = [
                c for c in candidates
                if str(c.get('name', '')).strip() in selected_names
                or str(c.get('candidate_name', '')).strip() in selected_names
            ]
            print(f"📍 Sélection manuelle appliquée: {len(candidates)} candidat(s)")
        elif limit:
            candidates = candidates[:limit]
            print(f"📍 Limité au top {limit} candidat(s)")
        
        # Show all candidates with their scores
        print(f"\n📋 Candidats à formater ({len(candidates)}):")
        print(f"   {'#':<4} {'Candidat':<30} {'Score Final':>12} {'Statut':>10}")
        print(f"   {'-'*4} {'-'*30} {'-'*12} {'-'*10}")
        
        for idx, c in enumerate(candidates, 1):
            name = c.get('name', 'Inconnu')[:29]
            score = c.get('final_score', 0)
            score_display = f"{int(round(score))}%"
            status = "✅" if score >= SCORE_THRESHOLD else f"⚠️ <{int(SCORE_THRESHOLD)}%"
            print(f"   {idx:<4} {name:<30} {score_display:>12} {status:>10}")
        
        # Check for candidates below threshold
        below_threshold = check_candidates_below_threshold(candidates)

        if below_threshold and not args.skip_threshold_check and not args.non_interactive:
            filtered_candidates = prompt_threshold_confirmation(below_threshold, candidates)

            if not filtered_candidates:
                print(f"\n⏭️  Session {folder.name} ignorée.")
                continue

            session_stats = process_from_final_result(
                folder.name,
                limit=None,  # Already applied
                template_name=template_name,
                skip_threshold_check=True,
                pre_filtered_candidates=filtered_candidates,
            )
        else:
            if below_threshold and (args.skip_threshold_check or args.non_interactive):
                print(f"\n⚠️  Mode non-interactif: seuil ignoré ({int(SCORE_THRESHOLD)}%).")
            else:
                print(f"\n✅ Tous les candidats ont un score ≥ {int(SCORE_THRESHOLD)}%")
            session_stats = process_from_final_result(
                folder.name,
                limit=None,  # Already applied
                template_name=template_name,
                skip_threshold_check=True,
                pre_filtered_candidates=candidates,
            )

    if session_stats.get("total", 0) > 0 and session_stats.get("success", 0) == 0:
        print(
            f"\n❌ Échec du formatage: 0/{session_stats['total']} CV(s) généré(s). "
            "Vérifiez les logs de la session."
        )
        sys.exit(1)
    
    print("\n" + "="*70)
    print("✅ Terminé. Consultez le dossier 'logs' pour le détail par session.")
    if PLAYWRIGHT_READY:
        print("   📄 HTML + PDF générés")
    else:
        print("   ⚠️  HTML uniquement (PDF non disponible)")
    print("="*70)
