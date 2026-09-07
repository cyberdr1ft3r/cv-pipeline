import os
import sys
import json
import time
import logging
import re
import shutil
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher
from pypdf import PdfReader
from openai import OpenAI
from pathlib import Path
import yaml
from dotenv import load_dotenv
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from docx import Document
import ssl
import certifi

try:
    from script.offer_extractor import extract_offer_text, save_offer_to_session
    from script.experience_years import enrich_annees_experience
except ModuleNotFoundError:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from script.offer_extractor import extract_offer_text, save_offer_to_session
    from script.experience_years import enrich_annees_experience

# ================================
# LOAD ENV (EXPLICIT PATH)
# ================================
ENV_PATH = Path(__file__).resolve().parents[1] / "config" / ".env"
if not ENV_PATH.exists():
    raise FileNotFoundError(f"Environment file not found: {ENV_PATH}")
load_dotenv(dotenv_path=ENV_PATH)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError(
        f"❌ OPENROUTER_API_KEY is not defined. "
        f"Expected in {ENV_PATH}"
    )

# ================================
# PROJECT ROOT
# ================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ================================
# LOAD CONFIG
# ================================
CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Paths set via interactive dialog (required)
INPUT_DIR = None  # Path to CVs directory (set by user)
JOB_OFFER_PATH = None  # Path to job offer file (set by user)

# Session ID (timestamp-based, shared between offer and output)
SESSION_ID = None  # Format: YYYYMMDDHHMMSS

# Output paths from config (base paths, session-specific paths set later)
# Action 227: data folders resolve under DATA_ROOT via the shared resolver.
try:
    from script.storage_paths import CURRENT_DIR, ARCHIVE_DIR, safe_relpath
except ImportError:
    from storage_paths import CURRENT_DIR, ARCHIVE_DIR, safe_relpath

OUTPUT_DIR_BASE = CURRENT_DIR / "intermediary_structured"
OFFER_DIR_BASE = CURRENT_DIR / "offer"
FAILED_DIR_BASE = CURRENT_DIR / "failed"
LOG_DIR_BASE = CURRENT_DIR / "logs"
ARCHIVE_DIR_BASE = ARCHIVE_DIR

# Session-specific paths (will be set when session starts)
OUTPUT_DIR = None  # OUTPUT_DIR_BASE / SESSION_ID
FAILED_DIR = None  # FAILED_DIR_BASE / SESSION_ID  
FAILURE_LOG_PATH = None  # LOG_DIR_BASE / SESSION_ID / "failed_files.json"
ARCHIVE_DIR = None  # ARCHIVE_DIR_BASE / SESSION_ID

# Track failed files for end-of-session report
SESSION_FAILURES = []  # List of {filename, error, attempts}

os.makedirs(OUTPUT_DIR_BASE, exist_ok=True)
os.makedirs(OFFER_DIR_BASE, exist_ok=True)
os.makedirs(FAILED_DIR_BASE, exist_ok=True)
os.makedirs(LOG_DIR_BASE, exist_ok=True)
os.makedirs(ARCHIVE_DIR_BASE, exist_ok=True)

# ================================
# LOAD PROMPTS FROM FILES
# ================================
def load_prompt(prompt_key):
    """Load prompt template from external file
    
    Args:
        prompt_key: Key from CONFIG["prompts"] (e.g., "extraction", "validation", "spelling")
        
    Returns:
        str: The prompt template content
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
        KeyError: If prompt_key not in config
    """
    try:
        # Get path from config (relative to config directory)
        relative_path = CONFIG["prompts"][prompt_key]
        prompt_path = PROJECT_ROOT / "config" / relative_path
        
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}\n"
                f"Expected location: {safe_relpath(prompt_path)}"
            )
        
        # Load prompt content
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        # Validate it's not empty
        if not prompt_template.strip():
            raise ValueError(f"Prompt file is empty: {prompt_path.name}")
        
        return prompt_template
        
    except KeyError:
        print(f"❌ Prompt key '{prompt_key}' not found in config")
        print(f"Available keys: {list(CONFIG.get('prompts', {}).keys())}")
        raise
    except Exception as e:
        print(f"❌ Failed to load prompt '{prompt_key}': {e}")
        raise


# Load all prompts at startup
try:
    print("📝 Loading prompt templates...")
    EXTRACTION_PROMPT_TEMPLATE = load_prompt("extraction")
    VALIDATION_PROMPT_TEMPLATE = load_prompt("validation")
    SPELLING_PROMPT_TEMPLATE = load_prompt("spelling")
    print(f"✅ Loaded {len(CONFIG['prompts'])} prompt template(s)\n")
except Exception as e:
    print(f"❌ Failed to load prompts: {e}")
    print("Please ensure prompt files exist in config/prompts/")
    raise

# ================================
# LOGGING CONFIGURATION
# ================================
def setup_console_logging():
    """Setup console-only logging for initial startup (before session starts)"""
    logger = logging.getLogger("CVExtractor")
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Console handler only - no file yet
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(message)s")  # Simplified console format
    )

    logger.addHandler(console_handler)
    return logger


def setup_session_logging(log_dir):
    """Setup full logging with file handler for session-specific directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"extraction_{timestamp}.log")

    logger = logging.getLogger("CVExtractor")
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # File handler - detailed logs
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console handler - clean output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(message)s")  # Simplified console format
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"📋 Log file: {os.path.basename(log_file)}")
    return logger


# Initialize with console-only logging (no file created yet)
logger = setup_console_logging()

# ================================
# SSL CERTIFICATE SETUP (Windows Fix)
# ================================
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    logger.info("✅ SSL certificates configured")
except ImportError:
    logger.warning("⚠️  certifi not found, installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "certifi", "--quiet"])
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    logger.info("✅ SSL certificates installed and configured")

# ================================
# OPENROUTER CLIENT
# ================================
client = OpenAI(
    base_url=CONFIG["api"]["base_url"],
    api_key=OPENROUTER_API_KEY,
)

# ================================
# FAILURE TRACKING SYSTEM
# ================================
def init_failure_log():
    """Initialize a new failure log for the current session"""
    return {
        "session_id": SESSION_ID,
        "started_at": datetime.now().isoformat(),
        "failures": [],
        "last_updated": None
    }


def load_failure_log() -> Dict:
    """Load existing failure log or create new one"""
    if FAILURE_LOG_PATH and FAILURE_LOG_PATH.exists():
        try:
            with open(FAILURE_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return init_failure_log()


def save_failure_log(failure_log: Dict):
    """Save failure log to disk"""
    if not FAILURE_LOG_PATH:
        return
    failure_log["last_updated"] = datetime.now().isoformat()
    with open(FAILURE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(failure_log, f, ensure_ascii=False, indent=2)


def log_failure(filename: str, error_type: str, error_message: str, 
                attempt_number: int, model_used: str, stage: str):
    """Log a failure with details for later analysis"""
    global SESSION_FAILURES
    
    failure_log = load_failure_log()
    
    # Check if this file already has an entry
    existing_entry = next(
        (f for f in failure_log["failures"] if f["filename"] == filename), 
        None
    )
    
    failure_record = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type,
        "error_message": str(error_message)[:500],  # Truncate long messages
        "attempt_number": attempt_number,
        "model_used": model_used,
        "stage": stage
    }
    
    if existing_entry:
        # Update existing entry
        existing_entry["attempts"] = existing_entry.get("attempts", [])
        existing_entry["attempts"].append(failure_record)
        existing_entry["total_attempts"] = len(existing_entry["attempts"])
        existing_entry["last_attempt"] = failure_record["timestamp"]
        existing_entry["final_error"] = str(error_message)[:200]
    else:
        # Create new entry
        new_entry = {
            "filename": filename,
            "first_attempt": failure_record["timestamp"],
            "last_attempt": failure_record["timestamp"],
            "total_attempts": 1,
            "final_error": str(error_message)[:200],
            "attempts": [failure_record]
        }
        failure_log["failures"].append(new_entry)
    
    save_failure_log(failure_log)


def record_final_failure(filename: str, error: str, total_attempts: int):
    """Record a CV that has definitively failed after all retries"""
    global SESSION_FAILURES
    SESSION_FAILURES.append({
        "filename": filename,
        "error": error,
        "attempts": total_attempts
    })


def move_to_failed(source_path: str, filename: str):
    """Move a failed file to the session's failed directory (creates dir only when needed)"""
    if not FAILED_DIR:
        return
    # Create failed directory only when first file fails
    os.makedirs(FAILED_DIR, exist_ok=True)
    dest_path = os.path.join(FAILED_DIR, filename)
    try:
        shutil.copy2(source_path, dest_path)  # Copy instead of move to keep original
        logger.debug(f"   📁 Copied to failed: {filename}")
    except Exception as e:
        logger.warning(f"   ⚠️ Could not copy file to failed dir: {e}")


def display_failed_cvs_report():
    """Display a detailed report of all failed CVs at end of session"""
    global SESSION_FAILURES
    
    if not SESSION_FAILURES:
        return
    
    logger.info("")
    logger.info("🚨" + "=" * 68)
    logger.info("🚨 FAILED CVs REPORT")
    logger.info("🚨" + "=" * 68)
    
    for idx, failure in enumerate(SESSION_FAILURES, 1):
        logger.error(f"")
        logger.error(f"   {idx}. {failure['filename']}")
        logger.error(f"      Attempts: {failure['attempts']}")
        logger.error(f"      Error: {failure['error'][:100]}..." if len(failure['error']) > 100 else f"      Error: {failure['error']}")
    
    logger.info("")
    logger.info(f"📁 Failed CVs copied to: data/failed/{SESSION_ID}/")
    logger.info(f"📝 Detailed log saved to: data/logs/{SESSION_ID}/failed_files.json")
    logger.info("=" * 70)

# ================================
# IMPROVED JSON CLEANING
# ================================
def clean_json_response(text: str) -> Optional[str]:
    """Enhanced JSON extraction and cleaning"""
    if not text:
        return None

    # Remove markdown code blocks
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    # Extract JSON object
    start = text.find("{")
    end = text.rfind("}")
    
    if start == -1 or end == -1:
        logger.error("No valid JSON found in response")
        return None
    
    json_text = text[start : end + 1].strip()
    
    # Try to fix common JSON issues
    json_text = fix_common_json_issues(json_text)
    
    return json_text


def fix_common_json_issues(json_text: str) -> str:
    """Attempt to fix common JSON formatting issues"""
    
    # Remove trailing commas before closing brackets/braces
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
    
    # Fix missing commas between array elements
    json_text = re.sub(r'"\s*\n\s*"', '",\n"', json_text)
    
    # Fix missing commas between object properties
    json_text = re.sub(r'"\s*\n\s*"([^"]+)"\s*:', '",\n"\\1":', json_text)
    
    # Remove any BOM or special characters at the start
    json_text = json_text.lstrip('\ufeff\x00')
    
    return json_text


def aggressive_json_repair(text: str) -> Optional[Dict]:
    """Attempt aggressive JSON repair as last resort"""
    try:
        # Try to extract and parse incrementally
        lines = text.split('\n')
        depth = 0
        json_lines = []
        started = False
        
        for line in lines:
            if '{' in line and not started:
                started = True
            
            if started:
                json_lines.append(line)
                depth += line.count('{') - line.count('}')
                
                if depth == 0 and started:
                    break
        
        if json_lines:
            partial_json = '\n'.join(json_lines)
            partial_json = fix_common_json_issues(partial_json)
            return json.loads(partial_json)
            
    except Exception as e:
        logger.debug(f"Aggressive repair failed: {e}")
    
    return None


# ================================
# OPENROUTER CALL WITH RETRIES & FALLBACK
# ================================
def send_to_openrouter(prompt, model=None, retries=5, wait=10, use_fallback=True) -> Tuple[Optional[str], str]:
    """
    Send prompt to OpenRouter API with retry and fallback model support.
    
    Returns:
        Tuple of (response_content, model_used) or (None, last_model_tried) on failure
    """
    if model is None:
        model = CONFIG["api"]["model"]
    
    # Build list of models to try
    models_to_try = [model]
    if use_fallback:
        fallback_models = CONFIG["api"].get("fallback_models", [])
        models_to_try.extend(fallback_models)
    
    last_error = None
    
    for model_idx, current_model in enumerate(models_to_try):
        model_label = "primary" if model_idx == 0 else f"fallback-{model_idx}"
        
        for attempt in range(retries):
            try:
                logger.debug(f"API call [{model_label}] attempt {attempt + 1}/{retries} with {current_model}")
                response = client.chat.completions.create(
                    model=current_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=CONFIG["api"]["temperature"],
                    max_tokens=CONFIG["api"]["max_tokens"],
                )
                return response.choices[0].message.content, current_model
            except Exception as e:
                last_error = e
                logger.warning(f"API attempt {attempt + 1} with {current_model} failed: {e}")
                time.sleep(wait * (attempt + 1))  # Exponential backoff
        
        # If primary model failed all retries, try next model
        if model_idx < len(models_to_try) - 1:
            logger.info(f"   🔄 Switching to fallback model: {models_to_try[model_idx + 1]}")
    
    logger.error(f"❌ All OpenRouter attempts failed. Last error: {last_error}")
    return None, model

# ================================
# PDF TEXT EXTRACTION
# ================================
POPPLER_PATH = CONFIG["paths"]["POPPLER_PATH"]

# Suppress noisy PDF parsing warnings (font metadata issues)
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)

def extract_text_from_pdf(path):
    text = ""

    # ==========================
    # 1️⃣ pdfplumber (BEST)
    # ==========================
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text.strip() + "\n\n"
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}")

    # ==========================
    # 2️⃣ pypdf fallback
    # ==========================
    if len(text.strip()) < 100:
        try:
            reader = PdfReader(path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text.strip() + "\n\n"
        except Exception as e:
            logger.warning(f"pypdf failed: {e}")

    # ==========================
    # 3️⃣ OCR fallback (SCANNED PDF)
    # ==========================
    if len(text.strip()) < 100:
        logger.info(f"   🔍 OCR activated (scanned document)")
        try:
            images = convert_from_path(
                path,
                dpi=CONFIG["extraction"]["ocr_dpi"],
                poppler_path=POPPLER_PATH
            )

            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(
                    img,
                    lang="fra+eng"
                ) + "\n\n"

            text = ocr_text
            logger.info("   ✅ OCR completed")

        except Exception as e:
            logger.error(f"   ❌ OCR failed: {e}")

    return text.strip()


def get_validation_prompt(cv_text: str, extracted_json_text: str) -> str:
    """Enhanced validation prompt with strict JSON requirements"""
    json_preview = extracted_json_text[:2000] if extracted_json_text else ""
    
    # Escape curly braces in user data to prevent format() conflicts
    safe_cv_text = cv_text[:CONFIG["extraction"]["max_prompt_chars"]].replace("{", "{{").replace("}", "}}")
    safe_json_preview = json_preview.replace("{", "{{").replace("}", "}}")
    
    return VALIDATION_PROMPT_TEMPLATE.format(
        cv_text=safe_cv_text,
        json_preview=safe_json_preview
    )


def get_spelling_prompt(json_text: str) -> str:
    """Generate spelling correction prompt from template"""
    # Escape curly braces in JSON to prevent format() conflicts
    safe_json_text = json_text.replace("{", "{{").replace("}", "}}")
    return SPELLING_PROMPT_TEMPLATE.format(json_text=safe_json_text)

# ================================
# DUPLICATE PROJECT DETECTION
# ================================
def calculate_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def detect_duplicate_projects(projects, threshold=CONFIG["processing"]["duplicate_threshold"]):
    """Remove duplicate projects based on name and description similarity"""
    if not projects:
        return []
    
    unique = []
    removed = 0

    for p in projects:
        sig = f"{p.get('nom','')} {p.get('description','')}"
        duplicate = False

        for u in unique:
            u_sig = f"{u.get('nom','')} {u.get('description','')}"
            if calculate_similarity(sig, u_sig) >= threshold:
                duplicate = True
                removed += 1
                logger.debug(f"Duplicate project removed: {p.get('nom', 'Unknown')}")
                break

        if not duplicate:
            unique.append(p)

    if removed > 0:
        logger.info(f"   🔍 Removed {removed} duplicate project(s)")
    
    return unique

# ================================
# DATA VALIDATION & ENRICHMENT
# ================================

def fix_incorrect_structure(data):
    """Fix common structure issues where LLM uses wrong key names"""
    
    # Fix competences structure
    if "competences" in data:
        comp = data["competences"]
        
        # If using wrong structure, fix it
        if any(key in comp for key in ["langages", "frameworks", "cms", "bases_de_donnees", "methodologies", "autres"]):
            logger.warning("   ⚠️  Fixing incorrect competences structure...")
            
            # Collect all items into proper categories
            methodologies_et_outils = []
            technologies = []
            
            # Methodologies and tools
            if "methodologies" in comp:
                methodologies_et_outils.extend(comp["methodologies"])
            if "frameworks" in comp:
                # Some frameworks are actually tools (Docker, Jenkins, etc.)
                for item in comp["frameworks"]:
                    if item in ["Ansible", "Docker", "GitLab CI", "Helm", "Vault", "Terraform", 
                                "XL Deploy", "SoapUI", "Jenkins", "Kubernetes", "Jira", "Grafana", 
                                "SonarQube", "Tomcat", "HP ALM", "Dynatrace", "Enterprise Architect",
                                "Confluence", "Bitbucket", "Git", "Eclipse"]:
                        methodologies_et_outils.append(item)
                    else:
                        technologies.append(item)
            
            # Technologies
            if "langages" in comp:
                technologies.extend(comp["langages"])
            if "cms" in comp:
                technologies.extend(comp["cms"])
            if "bases_de_donnees" in comp:
                technologies.extend(comp["bases_de_donnees"])
            if "autres" in comp:
                technologies.extend(comp["autres"])
            
            # Also check if some items were put in wrong category
            remaining_frameworks = [f for f in comp.get("frameworks", []) 
                                   if f not in methodologies_et_outils and f not in technologies]
            technologies.extend(remaining_frameworks)
            
            # Replace with correct structure
            data["competences"] = {
                "methodologies_et_outils": list(set(methodologies_et_outils)),  # Remove duplicates
                "technologies": list(set(technologies))
            }
        
        # Even if structure is correct, clean up duplicates and wrong categorization
        if "methodologies_et_outils" in comp and "technologies" in comp:
            logger.info("   🔧 Cleaning competences categories...")
            
            # Define clear lists of what belongs where
            tools_keywords = [
                "Agile", "Scrum", "TDD", "UML", "ArchiMate", "DDD", "BPMN", "Merise",
                "Docker", "Kubernetes", "GitLab", "Jenkins", "Jira", "Confluence", "SonarQube",
                "Ansible", "Terraform", "Helm", "Vault", "Git", "Bitbucket", "GitLab CI",
                "XL Deploy", "SoapUI", "HP ALM", "Dynatrace", "Grafana", "Tomcat",
                "Enterprise Architect", "Eclipse", "ElasticSearch", "Scrum Master"
            ]
            
            methodologies = []
            technologies = []
            
            # Process methodologies_et_outils
            for item in comp.get("methodologies_et_outils", []):
                # Check if it's a tool/methodology
                is_tool = False
                for keyword in tools_keywords:
                    if keyword.lower() in item.lower():
                        is_tool = True
                        break
                
                if is_tool:
                    methodologies.append(item)
                else:
                    # It's actually a technology
                    technologies.append(item)
            
            # Process technologies (add all)
            technologies.extend(comp.get("technologies", []))
            
            # Remove duplicates and sort
            methodologies = sorted(list(set(methodologies)))
            technologies = sorted(list(set(technologies)))
            
            # Update data
            data["competences"] = {
                "methodologies_et_outils": methodologies,
                "technologies": technologies
            }
            
            logger.info(f"   ✅ Cleaned: {len(methodologies)} methodologies/tools, {len(technologies)} technologies")
    
    # Fix experiences_professionnelles structure
    if "experiences_professionnelles" in data:
        fixed_experiences = []
        for exp in data["experiences_professionnelles"]:
            fixed_exp = {}
            
            # Fix key names
            fixed_exp["titre_poste"] = exp.get("titre_poste") or exp.get("poste", "")
            fixed_exp["entreprise"] = exp.get("entreprise", "")
            fixed_exp["lieu"] = exp.get("lieu", "")
            
            # Fix dates
            if "dates" in exp:
                fixed_exp["dates"] = exp["dates"]
            elif "periode" in exp and "duree" in exp:
                fixed_exp["dates"] = f"{exp['periode']} • {exp['duree']}"
            elif "periode" in exp:
                fixed_exp["dates"] = exp["periode"]
            else:
                fixed_exp["dates"] = ""
            
            fixed_exp["contexte"] = exp.get("contexte", "")
            
            # Fix missions (might be called responsabilites)
            fixed_exp["missions"] = exp.get("missions") or exp.get("responsabilites", [])
            
            # Fix environnement
            fixed_exp["environnement"] = exp.get("environnement", [])
            
            # Handle projects listed inside experience (WRONG - should be in projets_realises)
            if "projets" in exp:
                logger.warning(f"   ⚠️  Found projects inside experience '{fixed_exp['entreprise']}' - should be in projets_realises")
                # We'll need to extract these to projets_realises
                for proj in exp["projets"]:
                    if "projets_realises" not in data:
                        data["projets_realises"] = []
                    
                    data["projets_realises"].append({
                        "nom": proj.get("nom", ""),
                        "client_ou_contexte": fixed_exp["entreprise"],
                        "description": proj.get("description", ""),
                        "technologies": proj.get("technologies", []),
                        "source": "experience_professionnelle",
                        "experience_liee": fixed_exp["entreprise"]
                    })
            
            fixed_experiences.append(fixed_exp)
        
        data["experiences_professionnelles"] = fixed_experiences
    
    # Remove invalid keys
    invalid_keys = ["autres_informations"]
    for key in invalid_keys:
        if key in data:
            logger.warning(f"   ⚠️  Removing invalid key: {key}")
            del data[key]
    
    return data


def validate_and_enrich_json(data):
    """Validate JSON structure and add metadata"""
    
    # First, fix any incorrect structure from LLM
    data = fix_incorrect_structure(data)
    
    # Ensure all required top-level keys exist
    required_keys = [
        "informations_personnelles",
        "formation",
        "certifications",
        "competences",
        "projets_realises",
        "langues",
        "experiences_professionnelles"
    ]
    
    for key in required_keys:
        if key not in data:
            if key in ["formation", "certifications", "projets_realises", "langues", "experiences_professionnelles"]:
                data[key] = []
            elif key == "competences":
                data[key] = {"methodologies_et_outils": [], "technologies": []}
            elif key == "informations_personnelles":
                data[key] = {"nom_complet": "", "titre": ""}
    
    # Validate personal info
    if not data["informations_personnelles"].get("nom_complet"):
        logger.warning("   ⚠️  Missing 'nom_complet' in personal information")

    data.setdefault("profil_resume", {"description": "", "annees_experience": "", "specialisations": []})
    before_years = str(data["profil_resume"].get("annees_experience", "")).strip()
    enrich_annees_experience(data)
    after_years = str(data["profil_resume"].get("annees_experience", "")).strip()
    if not before_years and after_years:
        logger.info(f"   📅 annees_experience computed from experiences: {after_years}")
    
    # Remove duplicates from projects
    if data.get("projets_realises"):
        original_count = len(data["projets_realises"])
        data["projets_realises"] = detect_duplicate_projects(data["projets_realises"])
        removed_count = original_count - len(data["projets_realises"])
        
        # Add metadata
        data["projets_metadata"] = {
            "total_projets": len(data["projets_realises"]),
            "duplicates_removed": removed_count
        }
    
    # Log statistics
    stats = {
        "formations": len(data.get("formation", [])),
        "certifications": len(data.get("certifications", [])),
        "projets": len(data.get("projets_realises", [])),
        "experiences": len(data.get("experiences_professionnelles", [])),
        "langues": len(data.get("langues", []))
    }
    logger.info(f"   📊 Stats: {stats['formations']} formation(s), {stats['experiences']} expérience(s), {stats['projets']} projet(s), {stats['certifications']} certification(s)")
    
    return data

# ================================
# SINGLE CV PROCESSING WITH RETRY
# ================================
def process_single_cv(file: str, path: str, cv_retry_attempts: int = 3) -> Tuple[bool, Optional[str]]:
    """
    Process a single CV file with multiple retry attempts.
    
    Args:
        file: Filename
        path: Full path to file
        cv_retry_attempts: Number of times to retry the entire CV processing
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    last_error = None
    model_used = CONFIG["api"]["model"]
    
    for attempt in range(1, cv_retry_attempts + 1):
        try:
            if attempt > 1:
                logger.info(f"   🔄 Retry attempt {attempt}/{cv_retry_attempts}...")
                time.sleep(5 * attempt)  # Increasing delay between retries
            
            # Extract text depending on file type
            logger.info(f"   📖 Extracting text...")
            
            if file.lower().endswith(".pdf"):
                cv_text = extract_text_from_pdf(path)
            elif file.lower().endswith(".docx"):
                try:
                    doc = Document(path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    cv_text = "\n\n".join(paragraphs)
                except Exception as e:
                    raise ValueError(f"Failed to extract text from DOCX: {e}")
            
            if not cv_text or len(cv_text.strip()) < 100:
                raise ValueError("Extracted text is too short or empty")
            
            logger.info(f"   ✅ Extracted {len(cv_text):,} characters")

            # Generate structured prompt
            prompt = EXTRACTION_PROMPT_TEMPLATE.format(cv_text=cv_text)
            
            # Send to OpenRouter (with fallback models)
            logger.info(f"   🤖 Calling OpenRouter API...")
            raw_response, model_used = send_to_openrouter(prompt, use_fallback=(attempt > 1))

            if not raw_response:
                raise RuntimeError("No response received from OpenRouter")

            logger.debug(f"   Received response: {len(raw_response)} characters")

            # Clean and try to parse JSON from LLM response
            cleaned_json = clean_json_response(raw_response)

            parsed = None
            parse_attempts = []
            parsing_method = None
            
            # Attempt 1: Direct parsing
            if cleaned_json:
                try:
                    parsed = json.loads(cleaned_json)
                    parsing_method = "direct parse"
                    logger.info("   ✅ JSON parsed successfully (direct)")
                except json.JSONDecodeError as e:
                    parse_attempts.append(f"Direct parse: {e}")
                    logger.debug(f"   Direct parse failed: {e}")

            # Attempt 2: Validation/correction by model
            if not parsed:
                logger.info(f"   🔄 Requesting validation...")
                validation_prompt = get_validation_prompt(cv_text, cleaned_json or raw_response)
                validated_raw, _ = send_to_openrouter(validation_prompt, use_fallback=True)

                if validated_raw:
                    validated_clean = clean_json_response(validated_raw)
                    if validated_clean:
                        try:
                            parsed = json.loads(validated_clean)
                            parsing_method = "validation"
                            logger.info("   ✅ JSON parsed successfully (validation)")
                        except json.JSONDecodeError as e:
                            parse_attempts.append(f"Validation parse: {e}")
                            logger.debug(f"   Validation parse failed: {e}")

            # Attempt 3: Aggressive repair
            if not parsed and cleaned_json:
                logger.info(f"   🔧 Attempting aggressive repair...")
                parsed = aggressive_json_repair(cleaned_json)
                if parsed:
                    parsing_method = "aggressive repair"
                    logger.info("   ✅ JSON recovered (aggressive repair)")

            # Attempt 4: Try validation response with aggressive repair
            if not parsed and 'validated_clean' in locals() and validated_clean:
                logger.info(f"   🔧 Repair on validated response...")
                parsed = aggressive_json_repair(validated_clean)
                if parsed:
                    parsing_method = "validated + repair"
                    logger.info("   ✅ JSON recovered (validated + repair)")

            if not parsed:
                error_msg = "Failed to obtain valid JSON after all attempts"
                logger.error(f"   ❌ {error_msg}")
                for att in parse_attempts:
                    logger.debug(f"      - {att}")
                raise ValueError(error_msg)

            data = parsed

            # Validate and enrich data
            logger.info(f"   🔍 Validating data...")
            data = validate_and_enrich_json(data)

            # Spelling correction (optional, only if successfully parsed)
            try:
                logger.info(f"   📝 Running spelling correction...")
                spelling_prompt = get_spelling_prompt(json.dumps(data, ensure_ascii=False, indent=2))
                spelling_raw, _ = send_to_openrouter(spelling_prompt, use_fallback=False)
                if spelling_raw:
                    spelling_clean = clean_json_response(spelling_raw)
                    if spelling_clean:
                        try:
                            spelling_data = json.loads(spelling_clean)
                            data = spelling_data
                            logger.info("   ✅ Spelling corrections applied")
                        except json.JSONDecodeError:
                            logger.debug("   Spelling-corrected JSON invalid; keeping previous data")
            except Exception as e:
                logger.warning(f"   ⚠️  Spelling correction failed: {e}")

            # Save JSON output
            if file.lower().endswith('.pdf'):
                out_filename = file.replace('.pdf', '.json')
            elif file.lower().endswith('.docx'):
                out_filename = file.replace('.docx', '.json')
            else:
                out_filename = f"{file}.json"
            out_path = os.path.join(OUTPUT_DIR, out_filename)
            
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"   💾 JSON saved: {out_filename}")

            # Archive the document
            archive_path = os.path.join(ARCHIVE_DIR, file)
            shutil.copy2(path, archive_path)
            logger.debug(f"   📦 Archived to: {os.path.basename(archive_path)}")

            return True, None
            
        except Exception as e:
            last_error = str(e)
            error_type = type(e).__name__
            
            # Log the failure attempt
            log_failure(
                filename=file,
                error_type=error_type,
                error_message=last_error,
                attempt_number=attempt,
                model_used=model_used,
                stage="processing"
            )
            
            logger.warning(f"   ⚠️  Attempt {attempt} failed: {last_error}")
            
            if attempt < cv_retry_attempts:
                continue
            else:
                break
    
    return False, last_error


# ================================
# MAIN PIPELINE
# ================================
def process_all_pdfs(input_dir: Path, job_offer_path: Path, max_cv_retries: int = 3, session_id: str = None):
    """
    Main pipeline to process all CVs with automatic retry handling.
    
    Args:
        input_dir: Path to directory containing CV files (required)
        job_offer_path: Path to job offer text file (required)
        max_cv_retries: Number of retry attempts per CV (default: 3)
        session_id: Optional session ID (if not provided, generates timestamp-based ID)
    """
    global INPUT_DIR, JOB_OFFER_PATH, SESSION_ID, OUTPUT_DIR, FAILED_DIR, FAILURE_LOG_PATH, SESSION_FAILURES, ARCHIVE_DIR, logger
    
    INPUT_DIR = input_dir
    JOB_OFFER_PATH = job_offer_path
    SESSION_FAILURES = []  # Reset for new session
    
    # Use provided session ID or generate new one
    SESSION_ID = session_id if session_id else datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Create session-specific directories
    session_offer_dir = OFFER_DIR_BASE / SESSION_ID
    OUTPUT_DIR = OUTPUT_DIR_BASE / SESSION_ID
    FAILED_DIR = FAILED_DIR_BASE / SESSION_ID  # Will only be created if needed
    ARCHIVE_DIR = ARCHIVE_DIR_BASE / SESSION_ID / "cvs" / "originals"  # Archive to cvs/originals subdirectory
    session_log_dir = LOG_DIR_BASE / SESSION_ID
    FAILURE_LOG_PATH = session_log_dir / "failed_files.json"
    
    os.makedirs(session_offer_dir, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # FAILED_DIR created only when first CV fails (see move_to_failed)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(session_log_dir, exist_ok=True)
    
    # Reconfigure logging to use session-specific directory (now creates file)
    logger = setup_session_logging(session_log_dir)
    
    # Copy job offer file to session offer directory
    # offer_dest = session_offer_dir / JOB_OFFER_PATH.name
    # shutil.copy2(JOB_OFFER_PATH, offer_dest)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🚀 CV EXTRACTION PIPELINE")
    logger.info("=" * 70)
    logger.info(f"🆔 Session ID: {SESSION_ID}")
    logger.info(f"📂 Input:  {INPUT_DIR}")
    logger.info(f"📄 Job offer: {JOB_OFFER_PATH.name} → data/offer/{SESSION_ID}/")
    logger.info(f"📂 Output: data/intermediary_structured/{SESSION_ID}/")
    logger.info(f"📂 Archive: data/archive/{SESSION_ID}/cvs/originals/")
    logger.info(f"📂 Failed: data/failed/{SESSION_ID}/ (only if failures occur)")
    logger.info(f"📂 Logs:   data/logs/{SESSION_ID}/")
    logger.info(f"🔁 Max retries per CV: {max_cv_retries}")
    logger.info("=" * 70)
    logger.info("")

    # Accept both PDF and DOCX files in input
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith((".pdf", ".docx"))]

    if not files:
        logger.warning("⚠️  No PDF/DOCX files found in input directory")
        logger.info("")
        return

    logger.info(f"📋 Found {len(files)} file(s) to process\n")
    
    success_count = 0
    failed_count = 0

    for idx, file in enumerate(files, 1):
        start = time.time()
        logger.info(f"┌{'─' * 68}┐")
        logger.info(f"│ [{idx}/{len(files)}] {file:<63}│")
        logger.info(f"└{'─' * 68}┘")

        path = os.path.join(INPUT_DIR, file)
        
        success, error = process_single_cv(file, path, cv_retry_attempts=max_cv_retries)
        
        elapsed = time.time() - start
        
        if success:
            logger.info(f"   ⏱️  Completed in {elapsed:.1f}s")
            logger.info(f"   ✅ SUCCESS\n")
            success_count += 1
        else:
            logger.error(f"   ❌ FAILED after {elapsed:.1f}s (all {max_cv_retries} attempts)")
            logger.error(f"   Error: {error}\n")
            
            # Copy to failed directory and record failure
            if os.path.exists(path):
                move_to_failed(path, file)
            
            record_final_failure(file, error, max_cv_retries)
            failed_count += 1

    # ============================================================
    # EXTRACT JOB OFFER TO TEXT FORMAT (after CV extraction)
    # ============================================================
    logger.info("")
    logger.info("=" * 70)
    logger.info("📄 JOB OFFER EXTRACTION PHASE")
    logger.info("=" * 70)

    if JOB_OFFER_PATH and JOB_OFFER_PATH.exists():
        offer_filename = JOB_OFFER_PATH.name
        offer_extension = JOB_OFFER_PATH.suffix.lower()
        
        logger.info(f"📋 Offer file: {offer_filename}")
        
        # Skip extraction if already .txt
        if offer_extension == '.txt':
            logger.info(f"✅ Offer is already .txt format - copying to session directory")
            session_offer_dir = OFFER_DIR_BASE / SESSION_ID
            os.makedirs(session_offer_dir, exist_ok=True)
            offer_dest = session_offer_dir / offer_filename
            shutil.copy2(JOB_OFFER_PATH, offer_dest)
            logger.info(f"   💾 Copied to: data/offer/{SESSION_ID}/{offer_filename}\n")
        else:
            logger.info(f"📊 Extracting from {offer_extension} format...")
            try:
                success, offer_text, method = extract_offer_text(JOB_OFFER_PATH)
                
                if success:
                    saved_path = save_offer_to_session(offer_text, SESSION_ID, offer_filename)
                    logger.info(f"   ✅ Offer extracted successfully using {method} method")
                    logger.info(f"   💾 Saved as .txt to: {safe_relpath(saved_path)}")
                    logger.info(f"   📏 Extracted {len(offer_text):,} characters\n")
                else:
                    logger.error(f"   ❌ Failed to extract offer: {offer_text}")
                    logger.error(f"   Matcher will fail gracefully if no offer found\n")
            except Exception as e:
                logger.error(f"   ❌ Unexpected error during offer extraction: {e}")
                logger.error(f"   Matcher will fail gracefully if no offer found\n")
    else:
        logger.warning("⚠️  No job offer file provided")
        logger.warning("   Matcher will fail gracefully if no offer found\n")

    # Final summary
    logger.info("=" * 70)
    logger.info("🏁 PIPELINE SUMMARY")
    logger.info("=" * 70)
    logger.info(f"🆔 Session:   {SESSION_ID}")
    logger.info(f"✅ Success:   {success_count:>3}")
    logger.info(f"❌ Failed:    {failed_count:>3}")
    logger.info(f"📊 Total:     {len(files):>3}")
    logger.info("=" * 70)
    
    # Display failed CVs report if any
    if failed_count > 0:
        display_failed_cvs_report()
    
    # # Cleanup: Remove original input files that were successfully archived
    # if success_count > 0:
    #     logger.info("")
    #     logger.info("🧹 Cleaning up input files...")
    #     cleaned_count = 0
    #     for file in files:
    #         input_path = Path(INPUT_DIR) / file
    #         archive_path = Path(ARCHIVE_DIR) / file
    #         # Only remove if successfully archived
    #         if archive_path.exists() and input_path.exists():
    #             try:
    #                 input_path.unlink()
    #                 cleaned_count += 1
    #             except Exception as e:
    #                 logger.warning(f"   ⚠️  Could not remove {file}: {e}")
    #     logger.info(f"   ✅ Removed {cleaned_count} input file(s)")
        
    #     # Remove input directory if empty
    #     try:
    #         if INPUT_DIR.exists() and not any(INPUT_DIR.iterdir()):
    #             INPUT_DIR.rmdir()
    #             logger.info(f"   ✅ Removed empty input directory")
    #     except Exception as e:
    #         logger.debug(f"   Could not remove input directory: {e}")
    
    logger.info("")


# ================================
# INTERACTIVE PATH INPUT
# ================================
def prompt_for_paths() -> Tuple[Path, Path]:
    """
    Prompt user for required paths via terminal dialog.
    
    Returns:
        Tuple of (input_dir, job_offer_path)
    """
    print("\n" + "=" * 70)
    print("📄 CV EXTRACTION PIPELINE - CONFIGURATION")
    print("=" * 70 + "\n")
    
    # Prompt for CVs directory
    while True:
        cv_path = input("📁 Enter the path to the CVs directory: ").strip()
        
        if not cv_path:
            print("❌ Path cannot be empty. Please try again.\n")
            continue
        
        # Remove quotes if user wrapped path in quotes
        cv_path = cv_path.strip('"').strip("'")
        input_dir = Path(cv_path)
        
        if not input_dir.exists():
            print(f"❌ Directory does not exist: {input_dir}")
            print("   Please enter a valid path.\n")
            continue
        
        if not input_dir.is_dir():
            print(f"❌ Path is not a directory: {input_dir}")
            print("   Please enter a path to a directory.\n")
            continue
        
        # Check if directory contains CV files
        cv_files = [f for f in os.listdir(input_dir) if f.lower().endswith((".pdf", ".docx"))]
        if not cv_files:
            print(f"⚠️  No PDF/DOCX files found in: {input_dir}")
            #proceed = input("   Do you want to continue anyway? (y/n): ").strip().lower()
            # if proceed != 'y':
                # continue
        else:
            print(f"✅ Found {len(cv_files)} CV file(s)\n")
            break
        
    
    # Prompt for job offer file
    while True:
        job_path = input("📄 Enter the path to the job offer file: ").strip()
        
        if not job_path:
            print("❌ Path cannot be empty. Please try again.\n")
            continue
        
        # Remove quotes if user wrapped path in quotes
        job_path = job_path.strip('"').strip("'")
        job_offer_path = Path(job_path)
        
        if not job_offer_path.exists():
            print(f"❌ File does not exist: {job_offer_path}")
            print("   Please enter a valid path.\n")
            continue
        
        if not job_offer_path.is_file():
            print(f"❌ Path is not a file: {job_offer_path}")
            print("   Please enter a path to a file.\n")
            continue
        
        print(f"✅ Job offer file found\n")
        break
    
    print("=" * 70 + "\n")
    return input_dir, job_offer_path


# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CV Extraction Pipeline - Automatically processes CVs with retry handling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 01_extraction_and_validation.py              # Interactive mode (prompts for paths)
  python 01_extraction_and_validation.py --retries 5  # 5 retries per CV (default: 3)
  python 01_extraction_and_validation.py --input ./cvs --offer ./job.txt  # Non-interactive

The script will:
  1. Prompt for CVs directory and job offer file paths (if not provided)
  2. Process all CVs with automatic retry (max 3 attempts by default)
  3. Save results in session-specific directories (using timestamp ID)
  4. Display a report of any failed CVs at the end
        """
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retry attempts per CV (default: 3)"
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Session ID to use (default: auto-generate timestamp)"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Path to directory containing CV files (PDF/DOCX)"
    )
    parser.add_argument(
        "--offer", "-o",
        type=str,
        default=None,
        help="Path to job offer file"
    )
    
    args = parser.parse_args()
    
    try:
        # Use CLI arguments if provided, otherwise prompt interactively
        if args.input and args.offer:
            input_dir = Path(args.input)
            job_offer_path = Path(args.offer)
            
            # Validate paths
            if not input_dir.exists() or not input_dir.is_dir():
                print(f"❌ CV directory not found: {input_dir}")
                sys.exit(1)
            if not job_offer_path.exists() or not job_offer_path.is_file():
                print(f"❌ Job offer file not found: {job_offer_path}")
                sys.exit(1)
        else:
            # Interactive dialog for paths
            input_dir, job_offer_path = prompt_for_paths()
        
        process_all_pdfs(
            input_dir=input_dir,
            job_offer_path=job_offer_path,
            max_cv_retries=args.retries,
            session_id=args.session
        )
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user\n")
    except Exception as e:
        logger.exception("\n💥 Fatal error in pipeline\n")
    finally:
        logger.info("👋 Pipeline terminated\n")