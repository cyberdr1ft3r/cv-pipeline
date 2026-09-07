# script/final_result.py
"""
Final Result Aggregation Module
Combines AI matching scores with candidate test scores to produce final rankings.
"""

import os
import json
import yaml
import time
import logging
import re
import csv
import argparse
import shutil
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# ================================
# CONFIGURATION
# ================================
ENV_PATH = Path(__file__).resolve().parents[1] / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError(f"❌ OPENROUTER_API_KEY is not defined. Expected in {ENV_PATH}")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "config" / "prompts"

CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Action 227: data folders resolve under DATA_ROOT via the shared resolver.
try:
    from script.storage_paths import CURRENT_DIR, safe_relpath
except ImportError:
    from storage_paths import CURRENT_DIR, safe_relpath

MATCHING_RESULTS_BASE = CURRENT_DIR / "matching_results"
FINAL_RESULT_BASE = CURRENT_DIR / "final_result"
LOG_DIR_BASE = CURRENT_DIR / "logs"
OFFER_DIR_BASE = CURRENT_DIR / "offer"
INTERMEDIARY_DIR_BASE = CURRENT_DIR / "intermediary_structured"
TESTS_DIR_BASE = CURRENT_DIR / "tests"

os.makedirs(FINAL_RESULT_BASE, exist_ok=True)
os.makedirs(LOG_DIR_BASE, exist_ok=True)
os.makedirs(TESTS_DIR_BASE, exist_ok=True)

try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except ImportError:
    pass

client = OpenAI(
    base_url=CONFIG["api"]["base_url"],
    api_key=OPENROUTER_API_KEY,
)

# ================================
# LOGGING
# ================================
def setup_console_logging():
    logger = logging.getLogger("FinalResult")
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)
    return logger


def setup_session_logging(log_dir: Path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"final_result_{timestamp}.log"
    logger = logging.getLogger("FinalResult")
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info(f"📋 Log file: {log_file.name}")
    return logger


logger = setup_console_logging()


# ================================
# PROMPT LOADING
# ================================
def load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


# ================================
# API CALLS
# ================================
def send_to_openrouter(prompt: str, retries: int = 5, wait: int = 10) -> Optional[str]:
    model = CONFIG["api"]["model"]
    fallback_models = CONFIG["api"].get("fallback_models", [])
    models_to_try = [model] + fallback_models
    
    for model_idx, current_model in enumerate(models_to_try):
        for attempt in range(retries):
            try:
                logger.debug(f"API call attempt {attempt + 1}/{retries} with {current_model}")
                response = client.chat.completions.create(
                    model=current_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=CONFIG["api"]["temperature"],
                    max_tokens=CONFIG["api"]["max_tokens"],
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"API attempt {attempt + 1} with {current_model} failed: {e}")
                time.sleep(wait * (attempt + 1))
        
        if model_idx < len(models_to_try) - 1:
            logger.info(f"   🔄 Switching to fallback model: {models_to_try[model_idx + 1]}")
    
    logger.error("❌ All OpenRouter attempts failed")
    return None


# ================================
# JSON UTILITIES
# ================================
def clean_json_response(text: str) -> Optional[str]:
    if not text:
        return None

    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    start = text.find("{")
    end = text.rfind("}")
    
    if start == -1 or end == -1:
        return None
    
    json_str = text[start:end + 1].strip()
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    return json_str


def repair_json(broken_json: str) -> Optional[str]:
    try:
        json.loads(broken_json)
        return broken_json
    except json.JSONDecodeError as e:
        error_pos = e.pos
        truncated = broken_json[:error_pos]
        
        last_complete = max(truncated.rfind('},'), truncated.rfind('}'))
        
        if last_complete > 0:
            truncated = truncated[:last_complete + 1]
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')
            truncated += ']' * open_brackets + '}' * open_braces
            
            try:
                json.loads(truncated)
                return truncated
            except:
                pass
    
    try:
        last_good_pos = broken_json.rfind('"},')
        if last_good_pos == -1:
            last_good_pos = broken_json.rfind('"}')
        
        if last_good_pos > 0:
            truncated = broken_json[:last_good_pos + 2]
            open_braces = truncated.count('{') - truncated.count('}')
            truncated += '}' * open_braces
            
            try:
                json.loads(truncated)
                return truncated
            except:
                pass
    except:
        pass
    
    return None


# ================================
# TEST SCORES PARSING
# ================================
def parse_test_scores_with_llm(csv_content: str, headers: List[str]) -> Dict[str, Any]:
    prompt_template = load_prompt("csv_test_scores_parsing_prompt.txt")
    prompt = prompt_template.format(
        headers=json.dumps(headers, indent=2),
        csv_content=csv_content
    )

    max_retries = CONFIG.get("api", {}).get("json_repair_retries", 3)
    last_error = None

    for attempt in range(max_retries):
        response = send_to_openrouter(prompt)
        
        if not response:
            last_error = "Failed to get LLM response for CSV parsing"
            continue
        
        cleaned = clean_json_response(response)
        if not cleaned:
            last_error = "Failed to extract JSON from LLM CSV parsing response"
            continue
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"   ⚠️  JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
            
            repaired = repair_json(cleaned)
            if repaired:
                try:
                    result = json.loads(repaired)
                    logger.info(f"   ✅ Successfully repaired JSON")
                    return result
                except json.JSONDecodeError:
                    pass
            
            last_error = f"Invalid JSON from LLM CSV parsing: {e}"
            
            if attempt < max_retries - 1:
                logger.info(f"   🔄 Retrying with fresh LLM call...")
    
    raise ValueError(last_error or "Failed to parse test scores after all retries")


def parse_test_scores_fallback(test_file_path: Path, headers: List[str]) -> Dict[str, Dict[str, Any]]:
    candidates = {}
    
    with open(test_file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        name_col = None
        email_col = None
        score_col = None
        alert_col = None
        tech_cols = {}
        
        for h in headers:
            h_lower = h.lower().strip()
            if h_lower == 'name':
                name_col = h
            elif h_lower == 'email':
                email_col = h
            elif 'score (%)' in h_lower or h_lower == 'score':
                score_col = h
            elif 'unusual activity' in h_lower or 'alert' in h_lower:
                alert_col = h
            elif '- points' in h_lower:
                parts = h.split(' - ')
                if len(parts) >= 2:
                    main_tech = parts[0].strip()
                    if main_tech not in tech_cols:
                        tech_cols[main_tech] = {'points': [], 'max': []}
                    tech_cols[main_tech]['points'].append(h)
            elif '- max points' in h_lower or '- maximum' in h_lower:
                parts = h.split(' - ')
                if len(parts) >= 2:
                    main_tech = parts[0].strip()
                    if main_tech not in tech_cols:
                        tech_cols[main_tech] = {'points': [], 'max': []}
                    tech_cols[main_tech]['max'].append(h)
        
        if not name_col:
            logger.warning("   ⚠️  Could not find 'Name' column in CSV")
            return {}
        
        for row in reader:
            name = row.get(name_col, "").strip()
            if not name:
                continue
            
            email = row.get(email_col, "").strip() if email_col else None
            
            test_score = 0.0
            if score_col:
                try:
                    score_str = row.get(score_col, "0").replace("%", "").strip()
                    test_score = float(score_str) if score_str else 0.0
                except (ValueError, TypeError):
                    pass
            
            technology_scores = {}
            for tech_name, cols in tech_cols.items():
                total_points = 0
                total_max = 0
                
                for pc in cols.get('points', []):
                    try:
                        val = float(row.get(pc, 0) or 0)
                        total_points += val
                    except (ValueError, TypeError):
                        pass
                
                for mc in cols.get('max', []):
                    try:
                        val = float(row.get(mc, 0) or 0)
                        total_max += val
                    except (ValueError, TypeError):
                        pass
                
                if total_max > 0:
                    technology_scores[tech_name] = {
                        "points": total_points,
                        "max_points": total_max,
                        "score_percent": round((total_points / total_max) * 100, 2)
                    }
            
            alerts = row.get(alert_col, "").strip() or None if alert_col else None
            
            candidates[name] = {
                "email": email,
                "test_score": round(test_score, 2),
                "technology_scores": technology_scores,
                "unusual_activity_alerts": alerts
            }
    
    logger.info(f"   ✅ Parsed {len(candidates)} candidates from CSV (fallback mode)")
    return candidates


def parse_test_scores(test_file_path: Path) -> Dict[str, Dict[str, Any]]:
    if not test_file_path.exists():
        raise FileNotFoundError(f"Test scores file not found: {test_file_path}")
    
    with open(test_file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    with open(test_file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
    
    logger.info("   🤖 Using LLM to parse complex CSV structure...")
    try:
        parsed_data = parse_test_scores_with_llm(content, headers)
        
        candidates = {}
        for name, data in parsed_data.get("candidates", {}).items():
            candidates[name] = {
                "email": data.get("email"),
                "test_score": round(float(data.get("test_score", 0)), 2),
                "technology_scores": data.get("technology_scores", {}),
                "unusual_activity_alerts": data.get("unusual_activity_alerts")
            }
        
        return candidates
        
    except (ValueError, RuntimeError) as e:
        logger.warning(f"   ⚠️  LLM parsing failed: {e}")
        logger.info("   📊 Falling back to direct CSV parsing...")
        return parse_test_scores_fallback(test_file_path, headers)


# ================================
# CANDIDATE EMAIL EXTRACTION FROM CVs
# ================================
def extract_emails_from_cvs(session_id: str, cv_dir: Optional[Path] = None) -> Dict[str, str]:
    from storage_paths import resolve_session_cv_dir

    intermediary_dir = cv_dir or resolve_session_cv_dir(session_id)
    if not intermediary_dir or not intermediary_dir.exists():
        return {}

    email_map = {}
    for json_file in intermediary_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                cv_data = json.load(f)
            
            # Try multiple possible field names (French and English)
            name = (
                cv_data.get("informations_personnelles", {}).get("nom_complet") or
                cv_data.get("informations_personnelles", {}).get("full_name") or
                cv_data.get("personal_info", {}).get("full_name") or
                cv_data.get("nom_complet") or
                cv_data.get("name", "")
            )
            
            email = (
                cv_data.get("informations_personnelles", {}).get("email") or
                cv_data.get("personal_info", {}).get("email") or
                cv_data.get("email", "")
            )
            
            if name and email:
                email_map[name] = email.lower().strip()
        except (json.JSONDecodeError, KeyError):
            continue
    
    return email_map


# ================================
# CANDIDATE MATCHING
# ================================
def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(name).lower().strip())


def _sorted_name_tokens(name: str) -> List[str]:
    return sorted(_normalize_name(name).split())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _tokens_subset_match(name_a: str, name_b: str) -> bool:
    tokens_a = _sorted_name_tokens(name_a)
    tokens_b = _sorted_name_tokens(name_b)
    if tokens_a == tokens_b:
        return True
    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    longer_set = set(longer)
    return all(token in longer_set for token in shorter)


def _match_confidence(
    cv_name: str,
    csv_name: str,
    cv_email: Optional[str],
    csv_email: Optional[str],
) -> Tuple[int, str]:
    norm_cv = _normalize_name(cv_name)
    norm_csv = _normalize_name(csv_name)

    if norm_cv and norm_cv == norm_csv:
        return 100, "exact"

    cv_em = (cv_email or "").lower().strip()
    csv_em = (csv_email or "").lower().strip()
    if cv_em and csv_em and cv_em == csv_em:
        return 100, "email"

    if _sorted_name_tokens(cv_name) == _sorted_name_tokens(csv_name):
        return 95, "token_order"

    if _tokens_subset_match(cv_name, csv_name):
        return 90, "token_subset"

    distance = _levenshtein(norm_cv, norm_csv)
    if distance <= 2:
        return max(70, 88 - distance * 4), "levenshtein"

    return 0, "none"


def match_candidates_fuzzy(
    matching_candidates: List[Dict[str, Any]],
    test_scores: Dict[str, Dict[str, Any]],
    cv_emails: Dict[str, str],
) -> Tuple[Dict[str, Optional[str]], Dict[str, Dict[str, Any]]]:
    """
    Match pipeline candidates to CoderPad CSV rows using deterministic fuzzy logic.

    Priority: exact name → email → sorted tokens (reversed names) →
    token subset → Levenshtein ≤ 2 on full normalized name.
    """
    csv_names = list(test_scores.keys())
    pairs: List[Tuple[int, str, str, str]] = []

    for candidate in matching_candidates:
        cv_name = candidate.get("candidate_name", "Unknown")
        cv_email = cv_emails.get(cv_name, "")
        for csv_name in csv_names:
            csv_email = test_scores[csv_name].get("email")
            confidence, method = _match_confidence(cv_name, csv_name, cv_email, csv_email)
            if confidence > 0:
                pairs.append((confidence, cv_name, csv_name, method))

    pairs.sort(key=lambda item: item[0], reverse=True)

    matches: Dict[str, Optional[str]] = {
        candidate.get("candidate_name", "Unknown"): None
        for candidate in matching_candidates
    }
    meta: Dict[str, Dict[str, Any]] = {}
    used_csv: set = set()
    used_cv: set = set()

    for confidence, cv_name, csv_name, method in pairs:
        if cv_name in used_cv or csv_name in used_csv:
            continue
        matches[cv_name] = csv_name
        meta[cv_name] = {
            "confidence": confidence,
            "name_matched_fuzzy": confidence < 100,
            "match_method": method,
        }
        used_cv.add(cv_name)
        used_csv.add(csv_name)

    for csv_name in csv_names:
        if csv_name not in used_csv:
            logger.warning(f"   ⚠️  No match for: '{csv_name}'")

    for cv_name, csv_name in matches.items():
        if not csv_name:
            continue
        entry = meta.get(cv_name, {})
        if entry.get("name_matched_fuzzy"):
            logger.info(
                f"   🔍 Fuzzy match: '{csv_name}' → '{cv_name}' "
                f"(confidence: {entry['confidence']}%)"
            )
        else:
            logger.info(f"   ✅ Matched: {cv_name} ↔ {csv_name}")

    return matches, meta


def match_candidates_with_llm(
    matching_candidates: List[Dict[str, Any]], 
    test_scores: Dict[str, Dict[str, Any]],
    cv_emails: Dict[str, str]
) -> Dict[str, Optional[str]]:
    
    source_a_data = []
    for candidate in matching_candidates:
        name = candidate.get("candidate_name", "Unknown")
        email = cv_emails.get(name, "")
        source_a_data.append({"name": name, "email": email})
    
    source_b_data = []
    for name, data in test_scores.items():
        email = data.get("email", "") or ""
        source_b_data.append({"name": name, "email": email})
    
    prompt_template = load_prompt("candidate_name_matching_prompt.txt")
    prompt = prompt_template.format(
        source_a_data=json.dumps(source_a_data, indent=2),
        source_b_data=json.dumps(source_b_data, indent=2)
    )
    
    response = send_to_openrouter(prompt)
    
    if not response:
        logger.warning("   ⚠️ LLM name matching failed, falling back to email matching")
        return fallback_email_matching(source_a_data, source_b_data)
    
    cleaned = clean_json_response(response)
    if not cleaned:
        logger.warning("   ⚠️ Failed to parse LLM response, falling back to email matching")
        return fallback_email_matching(source_a_data, source_b_data)
    
    try:
        matches = json.loads(cleaned)
        test_names = set(test_scores.keys())
        validated = {}
        for matching_name, test_name in matches.items():
            if test_name is not None and test_name in test_names:
                validated[matching_name] = test_name
            else:
                validated[matching_name] = None
        return validated
    except json.JSONDecodeError:
        logger.warning("   ⚠️ Invalid JSON from LLM, falling back to email matching")
        return fallback_email_matching(source_a_data, source_b_data)


def fallback_email_matching(source_a: List[Dict], source_b: List[Dict]) -> Dict[str, Optional[str]]:
    email_to_b_name = {}
    for item in source_b:
        if item.get("email"):
            email_to_b_name[item["email"].lower()] = item["name"]
    
    matches = {}
    for item in source_a:
        name = item["name"]
        email = (item.get("email") or "").lower()
        
        if email and email in email_to_b_name:
            matches[name] = email_to_b_name[email]
        else:
            matches[name] = None
    
    return matches


# ================================
# SESSION & FILE UTILITIES
# ================================
def find_matching_results(session_id: str) -> List[Path]:
    session_dir = MATCHING_RESULTS_BASE / session_id
    if not session_dir.exists():
        return []
    return list(session_dir.glob("match_*.json"))


def load_matching_results(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_offer_description(session_id: str) -> str:
    offer_dir = OFFER_DIR_BASE / session_id
    
    if not offer_dir.exists():
        raise FileNotFoundError(f"Offer directory not found for session {session_id}")
    
    offer_files = list(offer_dir.glob("*.txt"))
    
    if not offer_files:
        raise FileNotFoundError(f"No offer file found in {offer_dir}")
    
    with open(offer_files[0], "r", encoding="utf-8") as f:
        return f.read().strip()


def get_offer_name_for_session(session_id: str) -> Optional[str]:
    offer_dir = OFFER_DIR_BASE / session_id
    if not offer_dir.exists():
        return None
    
    for file in offer_dir.iterdir():
        if file.is_file() and file.suffix in ['.txt', '.pdf', '.docx']:
            return file.stem
    return None


def find_available_sessions() -> List[Tuple[str, Optional[str]]]:
    sessions = []
    if MATCHING_RESULTS_BASE.exists():
        for item in MATCHING_RESULTS_BASE.iterdir():
            if item.is_dir() and re.match(r'\d{14}', item.name):
                offer_name = get_offer_name_for_session(item.name)
                sessions.append((item.name, offer_name))
    return sorted(sessions, key=lambda x: x[0], reverse=True)


def _filter_matching_candidates(
    matching_candidates: List[Dict[str, Any]],
    selected_names: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Keep only candidates whose candidate_name is in the selection list."""
    if not selected_names:
        return matching_candidates
    selected = {name.strip().lower() for name in selected_names if str(name).strip()}
    if not selected:
        return matching_candidates
    filtered = [
        c for c in matching_candidates
        if (c.get("candidate_name") or "").strip().lower() in selected
    ]
    if not filtered:
        raise ValueError("Aucun candidat sélectionné ne correspond aux résultats du matching.")
    return filtered


# ================================
# MAIN PROCESSING
# ================================
def process_final_results(
    session_id: str,
    test_scores_path: Optional[Path] = None,
    cv_dir: Optional[Path] = None,
    selected_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Process final results for a session.
    
    Args:
        session_id: The session ID to process
        test_scores_path: Optional path to test scores CSV file. If None, final score = CV matching score.
    
    Returns:
        Dict containing the final results
    """
    global logger
    
    session_log_dir = LOG_DIR_BASE / session_id
    output_dir = FINAL_RESULT_BASE / session_id
    session_tests_dir = TESTS_DIR_BASE / session_id
    
    os.makedirs(session_log_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(session_tests_dir, exist_ok=True)
    
    # Track if test scores are available
    has_test_scores = test_scores_path is not None and test_scores_path.exists()
    
    if has_test_scores:
        test_scores_dest = session_tests_dir / test_scores_path.name
        if not test_scores_dest.exists():
            shutil.copy2(test_scores_path, test_scores_dest)
    
    logger = setup_session_logging(session_log_dir)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🏆 FINAL RESULT AGGREGATION")
    logger.info("=" * 70)
    logger.info(f"🆔 Session ID: {session_id}")
    if has_test_scores:
        logger.info(f"📄 Test scores: {test_scores_path.name}")
    else:
        logger.info("📄 Test scores: ⚠️  NON FOURNI (final score = CV matching score)")
    logger.info("=" * 70)
    logger.info("")
    
    logger.info("📊 Loading matching results...")
    matching_files = find_matching_results(session_id)
    
    if not matching_files:
        raise FileNotFoundError(f"No matching results found for session {session_id}")
    
    matching_file = matching_files[0]
    matching_data = load_matching_results(matching_file)
    logger.info(f"   ✅ Loaded: {matching_file.name}")
    logger.info(f"   📋 Candidates: {matching_data.get('total_candidates', 0)}")
    
    logger.info("")
    logger.info("📄 Loading job offer description...")
    try:
        offer_description = load_offer_description(session_id)
        logger.info(f"   ✅ Offer loaded ({len(offer_description)} chars)")
    except FileNotFoundError as e:
        logger.warning(f"   ⚠️  {e}")
        offer_description = "No offer description available"
    
    # Parse test scores only if file is provided
    test_scores = {}
    if has_test_scores:
        logger.info("")
        logger.info("📝 Parsing test scores from CSV...")
        test_scores = parse_test_scores(test_scores_path)
        logger.info(f"   ✅ Parsed {len(test_scores)} candidate(s) from CSV file")
        
        for name, data in test_scores.items():
            tech_count = len(data.get('technology_scores', {}))
            email = data.get('email', '')
            email_str = f" ({email})" if email else ""
            alerts = data.get('unusual_activity_alerts')
            alert_str = f" ⚠️ {alerts}" if alerts else ""
            logger.info(f"      - {name}{email_str}: {data['test_score']}% ({tech_count} technologies){alert_str}")
    else:
        logger.info("")
        logger.info("📝 Test scores: SKIPPED (no test file provided)")
        logger.info("   ℹ️  Final scores will be based on CV matching score only (100% weight)")
    
    logger.info("")
    logger.info("📧 Extracting emails from CV data...")
    cv_emails = extract_emails_from_cvs(session_id, cv_dir=cv_dir)
    logger.info(f"   ✅ Found {len(cv_emails)} email(s) in CV data")
    
    matching_candidates = matching_data.get("candidates", [])
    if selected_names:
        before = len(matching_candidates)
        matching_candidates = _filter_matching_candidates(matching_candidates, selected_names)
        logger.info(f"   🎯 Sélection manuelle : {len(matching_candidates)}/{before} candidat(s)")
    merged_candidates = []
    
    if has_test_scores:
        # With test scores: match candidates and merge data
        logger.info("")
        logger.info("🔗 Matching candidates between sources (fuzzy name + email)...")

        name_matches, match_meta = match_candidates_fuzzy(
            matching_candidates, test_scores, cv_emails,
        )

        for candidate in matching_candidates:
            candidate_name = candidate.get("candidate_name", "Unknown")
            overall_score = candidate.get("overall_score", 0)

            matched_name = name_matches.get(candidate_name)
            fuzzy_meta = match_meta.get(candidate_name, {})

            if matched_name:
                test_data = test_scores[matched_name]
                test_score = test_data["test_score"]
                technology_scores = test_data.get("technology_scores", {})
                unusual_alerts = test_data.get("unusual_activity_alerts")
            else:
                test_score = None
                technology_scores = {}
                unusual_alerts = None
                logger.warning(f"   ⚠️  No test score for: {candidate_name}")

            merged_candidates.append({
                "name": candidate_name,
                "overall_score": overall_score,
                "test_score": test_score,
                "technology_scores": technology_scores,
                "unusual_activity_alerts": unusual_alerts,
                "name_matched_fuzzy": fuzzy_meta.get("name_matched_fuzzy", False),
            })
    else:
        # Without test scores: use CV matching score only
        logger.info("")
        logger.info("📋 Preparing candidates (without test scores)...")
        
        for candidate in matching_candidates:
            candidate_name = candidate.get("candidate_name", "Unknown")
            overall_score = candidate.get("overall_score", 0)
            
            merged_candidates.append({
                "name": candidate_name,
                "overall_score": overall_score,
                "test_score": None,  # Explicitly set to None to indicate no test
                "technology_scores": {},
                "unusual_activity_alerts": None
            })
            logger.info(f"   📌 {candidate_name}: CV score = {overall_score}%")
    
    logger.info("")
    logger.info("🤖 Generating final rankings via LLM...")
    
    # Choose the appropriate prompt based on whether test scores are available
    if has_test_scores:
        prompt_template = load_prompt("final_result_prompt.txt")
        logger.info("   📊 Using weighted formula: 40% CV + 60% Test")
    else:
        prompt_template = load_prompt("final_result_no_test_prompt.txt")
        logger.info("   📊 Using CV matching score only (100% weight)")
    
    matching_summary = {
        "session_id": matching_data.get("session_id"),
        "job_title": matching_data.get("job_title"),
        "candidates": merged_candidates,
        "has_test_scores": has_test_scores
    }
    
    prompt = prompt_template.format(
        offer_description=offer_description,
        matching_data=json.dumps(matching_summary, indent=2),
        session_id=session_id,
        job_title=matching_data.get("job_title", "Unknown"),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    raw_response = send_to_openrouter(prompt)
    
    if not raw_response:
        raise RuntimeError("Failed to get response from LLM")
    
    logger.debug(f"   Raw response length: {len(raw_response)} chars")
    
    cleaned_json = clean_json_response(raw_response)
    
    if not cleaned_json:
        raise ValueError("Failed to extract JSON from LLM response")
    
    try:
        final_results = json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        logger.error(f"   ❌ JSON parse error: {e}")
        raise ValueError(f"Invalid JSON from LLM: {e}")

    if has_test_scores:
        fuzzy_by_name = {
            c.get("name"): c.get("name_matched_fuzzy", False)
            for c in merged_candidates
        }
        for candidate in final_results.get("candidates", []):
            name = candidate.get("name")
            if name in fuzzy_by_name:
                candidate["name_matched_fuzzy"] = fuzzy_by_name[name]

    output_file = output_dir / "final_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"   ✅ Results saved to: {safe_relpath(output_file)}")
    
    logger.info("")
    logger.info("=" * 90)
    logger.info("🏆 TOP 5 CANDIDATES")
    logger.info("=" * 90)
    
    candidates = final_results.get("candidates", [])
    top_5 = [c for c in candidates if c.get("rank", 99) <= 5]
    
    logger.info("")
    logger.info(f"     {'Rank':<6} {'Candidate Name':<25} {'Final':<10} {'AI Match':<10} {'Test':<10} {'Alerts':<20}")
    logger.info(f"     {'-'*6} {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*20}")

    medals = ["🥇", "🥈", "🥉", "🏅", "🎖️ "]

    for candidate in top_5:
        rank = candidate.get("rank", "?")
        name = candidate.get("name", "Unknown")[:24]
        final_score = candidate.get("final_score", 0) or 0
        overall = candidate.get("overall_score", 0) or 0
        test = candidate.get("test_score")  # Can be None
        unusual_alerts = candidate.get("unusual_activity_alerts") or "-"

        final_pct = f"{int(round(final_score))}%"
        overall_pct = f"{int(round(overall))}%"
        # Handle None test score (when no test file was provided)
        test_pct = f"{int(round(test))}%" if test is not None else "N/A"
        
        medal = medals[rank - 1] if 1 <= rank <= 5 else "🏆"
        alerts_display = unusual_alerts[:18] + ".." if len(str(unusual_alerts)) > 20 else unusual_alerts
        
        logger.info(f"  {medal}  #{rank:<5} {name:<25} {final_pct:<10} {overall_pct:<10} {test_pct:<10} {alerts_display:<20}")
    
    return final_results


# ================================
# INTERACTIVE INPUT
# ================================
def prompt_for_inputs() -> Tuple[str, Optional[Path]]:
    """
    Prompt user for session ID and optional test scores file.
    
    Returns:
        Tuple of (session_id, test_scores_path or None)
    """
    print("\n" + "=" * 70)
    print("🏆 FINAL RESULT AGGREGATION - CONFIGURATION")
    print("=" * 70 + "\n")
    
    sessions = find_available_sessions()
    
    if not sessions:
        print("❌ No sessions found in matching_results/")
        print("   Please run the matcher first to generate matching results.")
        raise SystemExit(1)
    
    print("📋 Available sessions:")
    for idx, (session_id, offer_name) in enumerate(sessions, 1):
        if offer_name:
            print(f"   {idx}. {session_id} - {offer_name}")
        else:
            print(f"   {idx}. {session_id}")
    
    print("")
    
    session_ids = [s[0] for s in sessions]
    
    while True:
        session_input = input("🆔 Enter session ID or number (from list above): ").strip()
        
        if not session_input:
            print("❌ Selection cannot be empty. Please try again.\n")
            continue
        
        if session_input.isdigit():
            idx = int(session_input) - 1
            if 0 <= idx < len(sessions):
                session_id = sessions[idx][0]
                break
            else:
                print(f"❌ Invalid selection. Enter 1-{len(sessions)}.\n")
                continue
        
        if session_input in session_ids:
            session_id = session_input
            break
        else:
            print(f"❌ Session not found: {session_input}")
            print("   Please enter a valid session ID.\n")
            continue
    
    print(f"✅ Selected session: {session_id}\n")
    
    # Test scores file is now OPTIONAL
    print("📄 Test Scores File (OPTIONAL)")
    print("   Press Enter to skip (final score = CV matching score)")
    print("   Or enter the path to the test scores CSV file\n")
    
    test_scores_path = None
    
    while True:
        test_path = input("📄 Path to test scores file [skip]: ").strip()
        
        # Empty input = skip test scores
        if not test_path:
            print("ℹ️  No test scores file provided")
            print("   → Final score will be based on CV matching score only\n")
            test_scores_path = None
            break
        
        test_path = test_path.strip('"').strip("'")
        test_scores_path = Path(test_path)
        
        if not test_scores_path.exists():
            print(f"❌ File does not exist: {test_scores_path}")
            print("   Enter a valid path or press Enter to skip.\n")
            continue
        
        if not test_scores_path.is_file():
            print(f"❌ Path is not a file: {test_scores_path}")
            print("   Enter a path to a file or press Enter to skip.\n")
            continue
        
        print(f"✅ Test scores file found")
        print(f"   → Final score will use weighted formula (40% CV + 60% Test)\n")
        break
    
    print("=" * 70 + "\n")
    return session_id, test_scores_path


# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Final Result Aggregation - Combines AI matching with test scores")
    parser.add_argument("--session", type=str, help="Session ID to process")
    parser.add_argument("--tests", type=str, help="Path to test scores file (optional)")
    parser.add_argument("--no-tests", action="store_true", help="Skip test scores (use CV matching score only)")
    parser.add_argument("--cv-dir", type=str, default=None, help="Override CV directory (offer_only: read from CV_Theque mount)")
    parser.add_argument("--candidates-file", type=str, default=None, help="Path to JSON file with explicit candidate names for final scoring")
    
    args = parser.parse_args()
    
    try:
        if args.session:
            # CLI mode with session ID provided
            session_id = args.session
            
            if args.no_tests:
                # Explicitly skip test scores
                test_scores_path = None
                print(f"ℹ️  Running without test scores (--no-tests flag)")
            elif args.tests:
                # Test scores file provided
                test_scores_path = Path(args.tests)
                if not test_scores_path.exists():
                    print(f"❌ Test scores file not found: {test_scores_path}")
                    raise SystemExit(1)
            else:
                # No test file specified - default to None (optional)
                test_scores_path = None
                print(f"ℹ️  No test scores file provided - using CV matching score only")
        else:
            # Interactive mode
            session_id, test_scores_path = prompt_for_inputs()
        
        cv_dir = Path(args.cv_dir) if args.cv_dir else None
        selected_names = None
        if args.candidates_file:
            try:
                with open(args.candidates_file, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                if isinstance(parsed, list):
                    selected_names = [str(n) for n in parsed if str(n).strip()]
            except Exception as e:
                print(f"⚠️  Impossible de lire la sélection de candidats ({args.candidates_file}): {e}")
        results = process_final_results(
            session_id, test_scores_path, cv_dir=cv_dir, selected_names=selected_names,
        )
        
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user\n")
    except Exception as e:
        logger.exception(f"\n💥 Fatal error: {e}\n")
    finally:
        logger.info("👋 Final result aggregation terminated\n")
