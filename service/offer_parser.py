from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional, Tuple, List
from functools import lru_cache
import hashlib
import yaml
import time

from openai import OpenAI
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from docx import Document

from service.logging_config import app_logger
from service.config import PROJECT_ROOT, CV_THEQUE_DIR


# ================================
# LOAD CONFIG
# ================================
CONFIG_PATH = PROJECT_ROOT / "config" / "config_yaml.yaml"
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
except Exception as e:
    app_logger.warning(f"Failed to load config from {CONFIG_PATH}: {e}")
    CONFIG = {"api": {}, "prompts": {}}


# ================================
# LOAD PROMPTS
# ================================
def load_prompt(prompt_key: str) -> str:
    """Load prompt template from external file.
    
    Args:
        prompt_key: Key from CONFIG["prompts"] (e.g., "offer_parser_profile_system")
        
    Returns:
        str: The prompt template content
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
        KeyError: If prompt_key not in config
    """
    try:
        if prompt_key not in CONFIG.get("prompts", {}):
            raise KeyError(f"Prompt key '{prompt_key}' not found in config")
        
        relative_path = CONFIG["prompts"][prompt_key]
        prompt_path = PROJECT_ROOT / "config" / relative_path
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if not content.strip():
            raise ValueError(f"Prompt file is empty: {prompt_path.name}")
        
        return content
    
    except Exception as e:
        app_logger.error(f"Failed to load prompt '{prompt_key}': {e}")
        raise


# Load all required prompts at module initialization
try:
    PROFILE_SYSTEM_PROMPT = load_prompt("offer_parser_profile_system")
    PROFILE_USER_PROMPT_TEMPLATE = load_prompt("offer_parser_profile_user")
    SENIORITY_SYSTEM_PROMPT = load_prompt("offer_parser_seniority_system")
    SENIORITY_USER_PROMPT_TEMPLATE = load_prompt("offer_parser_seniority_user")
    METADATA_SKILLS_RULES = load_prompt("offer_parser_metadata_skills_rules")
except Exception as e:
    app_logger.warning(f"Failed to load offer parser prompts: {e}. Using fallback mode.")
    PROFILE_SYSTEM_PROMPT = None
    PROFILE_USER_PROMPT_TEMPLATE = None
    SENIORITY_SYSTEM_PROMPT = None
    SENIORITY_USER_PROMPT_TEMPLATE = None
    METADATA_SKILLS_RULES = None


def _write_to_stdout_log(log_path: Path, message: str) -> None:
    """Write message to stdout log file."""
    if log_path:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")


def _write_to_stderr_log(log_path: Path, message: str) -> None:
    """Write message to stderr log file."""
    if log_path:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")


# Profile and seniority mappings (fallback only)
PROFILES = {
    "fullstack": ["fullstack", "full stack", "full_stack", "full-stack", "développeur fullstack", "développeur full stack"],
    "devops": ["devops", "dev ops", "dev-ops", "sre", "devops/sre", "devops sre", "ingénieur devops", "ingénieur devops/sre", "ingénieur devops sre"],
    "data_analyst": ["data analyst", "analyste de données", "data analyste"],
    "data_scientist": ["data scientist", "scientifique des données"],
    "data_engineer": ["data engineer", "ingénieur de données", "ingénieur data"],
    "backend": ["backend", "back-end", "back end", "développeur backend", "développeur back-end"],
    "frontend": ["frontend", "front-end", "front end", "développeur frontend", "développeur front-end"],
    "mobile": ["mobile", "android", "ios", "développeur mobile", "développeur android", "développeur ios"],
    "qa": ["qa", "quality assurance", "testeur", "tester", "quality engineer"],
    "product_manager": ["product manager", "chef de produit", "pm"],
    "scrum_master": ["scrum master", "scrum"],
    "project_manager": ["project manager", "chef de projet", "gestionnaire de projet"],
}

SENIORITY_LEVELS = {
    "junior": ["junior", "débutant", "0-2 ans", "1-2 ans", "moins de 2 ans", "0-1 an", "moins d'un an", "débutant complet"],
    "confirme": [
        "confirme", "confirmé", "intermédiaire", "2-5 ans", "3-5 ans", "moyen", "2 à 5 ans", "3 à 4 ans",
        "3+ ans", "3 ans minimum", "4 ans minimum", "5 ans minimum",
    ],
    "senior": ["senior", "5+ ans", "5 ans et plus", "expérimenté", "5 à 10 ans", "6 ans", "7 ans", "8 ans", "9 ans", "expérience solide"],
    "expert": ["expert", "lead", "principal", "10+ ans", "10 ans et plus", "architecte", "au moins 10 ans", "plus de 10 ans", "10 années", "15 ans", "15+ ans", "20 ans", "architecte senior", "tech lead"],
}


def _seniority_from_years(years: int) -> str:
    """Map minimum years of experience to seniority bucket (Action 182/185 thresholds)."""
    if years <= 2:
        return "junior"
    if years <= 5:
        return "confirme"
    if years <= 10:
        return "senior"
    return "expert"


_SENIORITY_DISPLAY_LABELS = {
    "junior": "Junior",
    "confirme": "Confirmé",
    "senior": "Senior",
    "expert": "Expert",
}


def _seniority_display_label(level_key: str) -> str:
    """Return French display label for an internal seniority bucket key."""
    return _SENIORITY_DISPLAY_LABELS.get(level_key, level_key)


def _resolve_experience_year_pair(low: int, high: int) -> Optional[int]:
    """Map an experience year pair to seniority years (range ceiling).

    Handles clean ranges (2/5 → 5) and OCR artifacts where « à » vanishes and the
    upper bound merges into the lower digit, e.g. « 2 à 5 ans » → OCR « 2 45 ans ».
    """
    if high <= 20:
        return max(low, high)
    if low <= 9 and 10 <= high <= 99:
        ocr_tail = high % 10
        if low <= ocr_tail <= 15:
            return max(low, ocr_tail)
    return None


def _extract_min_experience_years(text: str) -> Optional[int]:
    """Extract years-of-experience from offer text for seniority mapping.

    For ranges (e.g. « 2 à 5 ans »), uses the maximum — the target seniority ceiling.
    For minimum-threshold wording (« minimum N ans », « au moins N ans », « N+ ans »),
    returns N+1 so « minimum 2 ans » maps to Confirmé, not Junior (Action 258).
    """
    text_lower = text.lower().replace("–", "-").replace("—", "-")
    range_sep = r"(?:à|a|-)"

    for pattern in (
        rf"(\d+)\s*ans\s+minimum[^,;]{{0,60}},\s*(\d+)\s*ans\s+id[ée]alement",
        rf"exp[eé]rience\s+signf?ificative\s+de\s+(\d+)\s*{range_sep}\s*(\d+)\s*ans",
        rf"entre\s+(\d+)\s+et\s+(\d+)\s*ans",
        rf"de\s+(\d+)\s*{range_sep}\s*(\d+)\s*ans",
        rf"(\d+)\s*{range_sep}\s*(\d+)\s*ans",
        rf"(\d+)\s*{range_sep}\s*(\d+)\s*années",
    ):
        match = re.search(pattern, text_lower)
        if match:
            return max(int(match.group(1)), int(match.group(2)))

    # OCR: « à » dropped — « 2 à 5 ans » → « 2 45 ans » or « 2 5 ans »
    for pattern in (
        r"exp[eé]rience\s+signf?ificative\s+de\s+(\d{1,2})\s+(\d{1,2})\s+ans",
        r"de\s+(\d{1,2})\s+(\d{1,2})\s+ans",
        r"(\d{1,2})\s+(\d{1,2})\s+ans",
    ):
        match = re.search(pattern, text_lower)
        if match:
            years = _resolve_experience_year_pair(
                int(match.group(1)), int(match.group(2))
            )
            if years is not None:
                return years

    # Minimum-threshold mentions: recruiter wants at least N years → map using N+1
    # (e.g. « minimum 2 ans » → 3 → Confirmé, not Junior).
    for pattern in (
        r"(\d+)\+\s*ans",
        r"(\d+)\s*ans\s+minimum",
        r"minimum\s+requis[^0-9]{0,40}(\d+)\s*ans",
        r"minimum\s+(\d+)\s*ans",
        r"exp[eé]rience\s+minimale[^0-9]{0,30}(\d+)\s*ans",
        r"minimale[^0-9]{0,30}(\d+)\s*ans",
        r"au moins\s+(\d+)\s*ans",
    ):
        match = re.search(pattern, text_lower)
        if match:
            return int(match.group(1)) + 1

    # Plain year mentions — no minimum boost (e.g. « 5 ans d'expérience »).
    match = re.search(r"(?<!\d)(\d+)\s*ans", text_lower)
    if match:
        return int(match.group(1))
    return None


def _extract_experience_range(text: str) -> tuple[Optional[float], Optional[float]]:
    """Extract (min_years, max_years) from offer text for ref.experience_ranges."""
    if not text or not text.strip():
        return None, None

    text_lower = text.lower().replace("–", "-").replace("—", "-")
    range_sep = r"(?:à|a|-)"

    for pattern in (
        rf"(\d+)\s*ans\s+minimum[^,;]{{0,60}},\s*(\d+)\s*ans\s+id[ée]alement",
        rf"exp[eé]rience\s+signf?ificative\s+de\s+(\d+)\s*{range_sep}\s*(\d+)\s*ans",
        rf"entre\s+(\d+)\s+et\s+(\d+)\s*ans",
        rf"de\s+(\d+)\s*{range_sep}\s*(\d+)\s*ans",
        rf"(\d+)\s*{range_sep}\s*(\d+)\s*ans",
        rf"(\d+)\s*{range_sep}\s*(\d+)\s*années",
    ):
        match = re.search(pattern, text_lower)
        if match:
            lo, hi = int(match.group(1)), int(match.group(2))
            return float(min(lo, hi)), float(max(lo, hi))

    for pattern in (
        r"exp[eé]rience\s+signf?ificative\s+de\s+(\d{1,2})\s+(\d{1,2})\s+ans",
        r"de\s+(\d{1,2})\s+(\d{1,2})\s+ans",
        r"(\d{1,2})\s+(\d{1,2})\s+ans",
    ):
        match = re.search(pattern, text_lower)
        if match:
            years = _resolve_experience_year_pair(int(match.group(1)), int(match.group(2)))
            if years is not None:
                return float(years), float(years)

    for pattern in (
        r"(\d+)\+\s*ans",
        r"(\d+)\s*ans\s+minimum",
        r"minimum\s+requis[^0-9]{0,40}(\d+)\s*ans",
        r"minimum\s+(\d+)\s*ans",
        r"exp[eé]rience\s+minimale[^0-9]{0,30}(\d+)\s*ans",
        r"minimale[^0-9]{0,30}(\d+)\s*ans",
        r"au moins\s+(\d+)\s*ans",
    ):
        match = re.search(pattern, text_lower)
        if match:
            return float(int(match.group(1)) + 1), None

    for pattern, group in (
        (r"maximum\s+(\d+)\s*ans", 1),
        (r"au plus\s+(\d+)\s*ans", 1),
        (r"moins de\s+(\d+)\s*ans", 1),
        (r"jusqu['']?\s*a\s+(\d+)\s*ans", 1),
    ):
        match = re.search(pattern, text_lower)
        if match:
            return None, float(int(match.group(group)))

    exact = re.search(
        r"(?<!\d)(\d+)\s*ans\s+d['']exp[eé]rience",
        text_lower,
    )
    if exact:
        n = int(exact.group(1))
        return float(n), float(n)

    seniority_ranges = (
        (("profil expert", "profil d'expert", "expert recherch"), (11.0, None)),
        (("profil senior", "profil sénior", "senior recherch"), (6.0, 10.0)),
        (("profil confirm", "confirmé recherch", "confirme recherch"), (3.0, 5.0)),
        (("profil junior", "junior recherch", "débutant recherch"), (0.0, 2.0)),
    )
    for keywords, bounds in seniority_ranges:
        if any(k in text_lower for k in keywords):
            return bounds

    return None, None


_CONTRACT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("contrat à durée déterminée", "CDD"),
    ("contrat a duree determinee", "CDD"),
    ("contrat temporaire", "CDD"),
    (" cdd ", "CDD"),
    ("stage", "Stage"),
    ("stagiaire", "Stage"),
    ("alternance", "Alternance"),
    ("apprentissage", "Alternance"),
    ("freelance", "Freelance"),
    ("indépendant", "Freelance"),
    ("independant", "Freelance"),
    ("mission freelance", "Freelance"),
    ("régie", "Regie"),
    ("regie", "Regie"),
    ("prestation", "Regie"),
)


_CONTRACT_CODE_MAP: dict[str, str] = {
    "cdi": "CDI",
    "cdd": "CDD",
    "freelance": "Freelance",
    "stage": "Stage",
    "alternance": "Alternance",
    "regie": "Regie",
    "régie": "Regie",
}


def _contract_type_from_text(text: str) -> Optional[str]:
    """Detect contract type from explicit labels and keywords in offer text."""
    text_lower = text.lower().replace("–", "-").replace("—", "-")
    padded = f" {text_lower} "

    explicit = re.search(
        r"type\s+de\s+contrat\s*[:\-]\s*"
        r"(cdi|cdd|freelance|stage|alternance|r[eé]gie)\b",
        text_lower,
    )
    if explicit:
        return _CONTRACT_CODE_MAP.get(explicit.group(1), explicit.group(1).title())

    for keyword, code in _CONTRACT_KEYWORDS:
        if keyword in padded or keyword in text_lower:
            return code
    return None


def _detect_contract_type(text: str, llm_value: Optional[str] = None) -> str:
    """Detect contract type: offer text (explicit/keywords) beats LLM; CDI is last resort."""
    from_text = _contract_type_from_text(text)
    if from_text:
        return from_text

    if llm_value:
        cleaned = llm_value.strip()
        for code in ("CDI", "CDD", "Freelance", "Stage", "Alternance", "Regie"):
            if cleaned.lower() == code.lower():
                return code
        if cleaned:
            return cleaned

    return "CDI"


class OfferParser:
    """Parse job offers to extract profile and seniority information using LLM and CV_Theque."""

    _extract_min_experience_years = staticmethod(_extract_min_experience_years)
    _extract_experience_range = staticmethod(_extract_experience_range)
    _seniority_from_years = staticmethod(_seniority_from_years)

    def __init__(self, openrouter_api_key: Optional[str] = None, stdout_log: Optional[Path] = None, stderr_log: Optional[Path] = None):
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.client = None
        self.stdout_log = stdout_log
        self.stderr_log = stderr_log
        
        # Load model configuration from config
        self.primary_model = CONFIG.get("api", {}).get("model", "xiaomi/mimo-v2-flash")
        self.fallback_models = CONFIG.get("api", {}).get("fallback_models", [])
        self.max_retries = CONFIG.get("api", {}).get("max_retries", 5)
        self.retry_wait_seconds = CONFIG.get("api", {}).get("retry_wait_seconds", 5)
        self.timeout_seconds = CONFIG.get("api", {}).get("timeout_seconds", 120)
        self.temperature = CONFIG.get("api", {}).get("temperature", 0.1)
        self.max_tokens = CONFIG.get("api", {}).get("max_tokens", 50)
        
        if self.openrouter_api_key:
            try:
                self.client = OpenAI(
                    api_key=self.openrouter_api_key,
                    base_url=CONFIG.get("api", {}).get("base_url", "https://openrouter.ai/api/v1"),
                )
                self._log("OpenRouter client initialized for offer parsing")
                self._log(f"Primary model: {self.primary_model}")
                if self.fallback_models:
                    self._log(f"Fallback models: {', '.join(self.fallback_models)}")
            except Exception as e:
                self._log_warning(f"Failed to initialize OpenRouter client: {str(e)}")
    
    def _log(self, message: str) -> None:
        """Write message to stdout log if available."""
        if self.stdout_log:
            _write_to_stdout_log(self.stdout_log, f"[OFFER PARSER] {message}")
        else:
            app_logger.info(f"[OFFER PARSER] {message}")
    
    def _log_warning(self, message: str) -> None:
        """Write warning message to stderr log if available."""
        if self.stderr_log:
            _write_to_stderr_log(self.stderr_log, f"[OFFER PARSER] WARNING: {message}")
        else:
            app_logger.warning(f"[OFFER PARSER] WARNING: {message}")
    
    def _log_error(self, message: str) -> None:
        """Write error message to stderr log if available."""
        if self.stderr_log:
            _write_to_stderr_log(self.stderr_log, f"[OFFER PARSER] ERROR: {message}")
        else:
            app_logger.error(f"[OFFER PARSER] ERROR: {message}")
    
    def _call_llm_with_fallback(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM with primary model, fall back to alternatives on failure."""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        
        models_to_try = [self.primary_model] + self.fallback_models
        
        for attempt, model in enumerate(models_to_try, 1):
            try:
                self._log(f"Attempting LLM call with model {attempt}/{len(models_to_try)}: {model}")
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout_seconds
                )
                
                result = response.choices[0].message.content.strip()
                self._log(f"LLM call succeeded with model: {model}")
                return result
            
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                self._log_warning(f"LLM call failed with {model}: {error_msg}")
                
                if attempt < len(models_to_try):
                    wait_time = self.retry_wait_seconds * (attempt ** 0.5)  # Exponential backoff
                    self._log(f"Waiting {wait_time:.1f}s before trying next model...")
                    time.sleep(wait_time)
                else:
                    self._log_error(f"All {len(models_to_try)} models failed. Last error: {error_msg}")
                    raise RuntimeError(f"LLM call failed after trying {len(models_to_try)} models: {error_msg}")
        
        raise RuntimeError("No models available for LLM call")

    @staticmethod
    def _normalize_profile_key(profile_name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", profile_name.lower())

    def _get_high_confidence_profile_hint(self, offer_text: str, available_profiles: List[str]) -> tuple[Optional[str], int]:
        """Return a strong keyword-based profile hint when the offer text is unambiguous."""
        text_lower = offer_text.lower()
        available_profile_keys = {self._normalize_profile_key(profile) for profile in available_profiles}

        best_profile_key: Optional[str] = None
        best_score = 0

        for profile_key, keywords in PROFILES.items():
            if available_profile_keys and profile_key not in available_profile_keys:
                continue

            score = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            if score > best_score:
                best_score = score
                best_profile_key = profile_key

        return best_profile_key, best_score
    
    def extract_text_from_file(self, file_path: Path) -> str:
        """Extract text from various file formats."""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        
        try:
            if suffix == '.txt':
                return file_path.read_text(encoding='utf-8')
            
            elif suffix == '.pdf':
                return self._extract_text_from_pdf(file_path)
            
            elif suffix in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                return self._extract_text_from_image(file_path)
            
            elif suffix in ['.doc', '.docx']:
                return self._extract_text_from_docx(file_path)
            
            elif suffix in ['.xls', '.xlsx', '.xlsm']:
                return self._extract_text_from_excel(file_path)
            
            else:
                raise ValueError(f"Unsupported file format: {suffix}")
        
        except Exception as e:
            app_logger.error(f"Failed to extract text from {file_path}: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            reader = PdfReader(str(file_path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            # If text extraction failed, try OCR
            if not text.strip():
                app_logger.warning(f"PDF text extraction failed for {file_path}, trying OCR")
                return self._extract_text_from_pdf_ocr(file_path)
            
            return text.strip()
        except Exception as e:
            self._log_error(f"PDF extraction failed: {str(e)}")
            raise
    
    def _extract_text_from_pdf_ocr(self, file_path: Path) -> str:
        """Extract text from PDF using OCR."""
        try:
            images = convert_from_path(str(file_path))
            text = ""
            for image in images:
                text += pytesseract.image_to_string(image) + "\n"
            return text.strip()
        except Exception as e:
            self._log_error(f"PDF OCR failed: {str(e)}")
            raise
    
    def _extract_text_from_image(self, file_path: Path) -> str:
        """Extract text from image using OCR."""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            self._log_error(f"Image OCR failed: {str(e)}")
            raise
    
    def _extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from Word document."""
        try:
            doc = Document(str(file_path))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            self._log_error(f"DOCX extraction failed: {str(e)}")
            raise
    
    def _extract_text_from_excel(self, file_path: Path) -> str:
        """Extract text from Excel file (.xls, .xlsx, .xlsm)."""
        suffix = Path(file_path).suffix.lower()
        if suffix == '.xls':
            return self._extract_text_from_xls(file_path)
        # .xlsx and .xlsm — openpyxl path (unchanged)
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(file_path))
            text = ""
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    row_text = " ".join(str(cell) if cell is not None else "" for cell in row)
                    text += row_text + "\n"
            return text.strip()
        except ImportError:
            self._log_error("openpyxl not installed for Excel processing")
            raise ValueError("Excel processing requires openpyxl package")
        except Exception as e:
            self._log_error(f"Excel extraction failed: {str(e)}")
            raise

    def _extract_text_from_xls(self, file_path: Path) -> str:
        """Extract text from legacy .xls files using xlrd.

        For multi-sheet workbooks, selects the sheet with the most total text
        content (by character count). This reliably targets the actual job
        description sheet over auxiliary sheets that are dense with numbers
        or template data.
        """
        try:
            import xlrd
        except ImportError:
            self._log_error("xlrd not installed for .xls processing")
            raise ValueError(".xls processing requires xlrd package")

        try:
            wb = xlrd.open_workbook(str(file_path))

            if wb.nsheets == 0:
                return ""

            # Pick the sheet with the most total text characters.
            target_sheet = wb.sheet_by_index(0)
            if wb.nsheets > 1:
                best_char_count = 0
                for i in range(wb.nsheets):
                    sheet = wb.sheet_by_index(i)
                    char_count = sum(
                        len(str(sheet.cell_value(r, c)))
                        for r in range(sheet.nrows)
                        for c in range(sheet.ncols)
                        if str(sheet.cell_value(r, c)).strip()
                    )
                    if char_count > best_char_count:
                        best_char_count = char_count
                        target_sheet = sheet

            text = ""
            for row_idx in range(target_sheet.nrows):
                row_text = " ".join(
                    str(target_sheet.cell_value(row_idx, col))
                    for col in range(target_sheet.ncols)
                    if str(target_sheet.cell_value(row_idx, col)).strip()
                )
                if row_text.strip():
                    text += row_text + "\n"

            return text.strip()

        except Exception as e:
            self._log_error(f".xls extraction failed: {str(e)}")
            raise
    
    @lru_cache(maxsize=100)
    def _get_available_profiles(self) -> List[str]:
        """Get available profiles from the mounted CV_Theque with caching."""
        try:
            profiles = sorted(p.name for p in CV_THEQUE_DIR.iterdir() if p.is_dir())
            self._log(f"Available profiles from CV_Theque: {profiles}")
            return profiles
        except Exception as e:
            self._log_error(f"Failed to get available profiles from CV_Theque: {str(e)}")
            return []
    
    @lru_cache(maxsize=100)
    def _get_available_seniority_levels(self, profile: str) -> List[str]:
        """Get available seniority levels for a profile from the mounted CV_Theque with caching."""
        try:
            levels = sorted(p.name for p in (CV_THEQUE_DIR / profile).iterdir() if p.is_dir())
            self._log(f"Available seniority levels for {profile}: {levels}")
            return levels
        except Exception as e:
            self._log_error(f"Failed to get available seniority levels for {profile}: {str(e)}")
            return []
    
    def _select_profile_with_llm(self, offer_text: str, available_profiles: List[str]) -> Optional[str]:
        """Use LLM to select the best matching profile from available options."""
        if not self.client or not available_profiles:
            return None
        
        try:
            # Create a hash of the offer text for caching
            offer_hash = hashlib.md5(offer_text.encode()).hexdigest()
            profiles_key = ",".join(sorted(available_profiles))
            cache_key = f"profile_selection_{offer_hash}_{profiles_key}"
            
            # Check if we have a cached result
            if hasattr(self, '_profile_cache') and cache_key in self._profile_cache:
                cached_result = self._profile_cache[cache_key]
                self._log(f"Using cached profile selection: {cached_result}")
                return cached_result
            
            # Use loaded prompts or fall back to inline defaults
            system_prompt = PROFILE_SYSTEM_PROMPT or "You are a job profile matcher. Select the best matching profile from available options."
            user_prompt_template = PROFILE_USER_PROMPT_TEMPLATE or """Analyze this job offer and select the BEST matching profile from available options.

Available profiles: {profiles}

Job Offer:
{offer_text}

Return ONLY the exact profile name from available list. If no profile is good match, return closest match.

Response format: Just the profile name, nothing else."""
            
            user_prompt = user_prompt_template.format(
                profiles=', '.join(available_profiles),
                offer_text=offer_text[:CONFIG.get("extraction", {}).get("max_prompt_chars", 3000)]
            )

            selected_profile = self._call_llm_with_fallback(system_prompt, user_prompt)

            # If the offer contains a very strong keyword signal, prefer it over a noisy LLM answer.
            keyword_profile, keyword_score = self._get_high_confidence_profile_hint(offer_text, available_profiles)
            if keyword_profile and keyword_score >= 2:
                normalized_selected = self._normalize_profile_key(selected_profile)
                if normalized_selected != keyword_profile:
                    self._log(
                        f"Overriding LLM profile '{selected_profile}' with high-confidence keyword match '{keyword_profile}' (score={keyword_score})"
                    )
                    selected_profile = keyword_profile
            
            # Validate the selected profile is in the available list
            if selected_profile not in available_profiles:
                self._log_warning(f"LLM selected invalid profile '{selected_profile}', not in available list")
                # Try to find closest match
                for profile in available_profiles:
                    if selected_profile.lower() in profile.lower() or profile.lower() in selected_profile.lower():
                        selected_profile = profile
                        break
                else:
                    # If still not found, return first available as fallback
                    selected_profile = available_profiles[0] if available_profiles else None
            
            # Cache the result
            if not hasattr(self, '_profile_cache'):
                self._profile_cache = {}
            self._profile_cache[cache_key] = selected_profile
            
            self._log(f"LLM selected profile: {selected_profile}")
            return selected_profile
        
        except Exception as e:
            self._log_error(f"LLM profile selection failed: {type(e).__name__}: {str(e)}")
            return None
    
    def _select_seniority_with_llm(self, offer_text: str, available_levels: List[str]) -> Optional[str]:
        """Use LLM to select the best matching seniority level from available options."""
        if not self.client or not available_levels:
            return None
        
        try:
            # Create a hash for caching
            offer_hash = hashlib.md5(offer_text.encode()).hexdigest()
            levels_key = ",".join(sorted(available_levels))
            cache_key = f"seniority_selection_{offer_hash}_{levels_key}"
            
            # Check cache
            if hasattr(self, '_seniority_cache') and cache_key in self._seniority_cache:
                cached_result = self._seniority_cache[cache_key]
                self._log(f"Using cached seniority selection: {cached_result}")
                return cached_result
            
            # Use loaded prompts or fall back to inline defaults
            system_prompt = SENIORITY_SYSTEM_PROMPT or "You are a job seniority matcher. Select the best matching seniority level from available options."
            user_prompt_template = SENIORITY_USER_PROMPT_TEMPLATE or """Analyze this job offer and select the BEST matching seniority level from available options.

Available seniority levels: {levels}

Job Offer:
{offer_text}

Return ONLY the exact seniority level name from available list. If no level is perfect match, return closest match.

Response format: Just the seniority level name, nothing else."""
            
            user_prompt = user_prompt_template.format(
                levels=', '.join(available_levels),
                offer_text=offer_text[:CONFIG.get("extraction", {}).get("max_prompt_chars", 3000)]
            )

            selected_level = self._call_llm_with_fallback(system_prompt, user_prompt)
            
            # Validate the selected level is in the available list
            if selected_level not in available_levels:
                self._log_warning(f"LLM selected invalid seniority '{selected_level}', not in available list")
                # Try to find closest match
                for level in available_levels:
                    if selected_level.lower() in level.lower() or level.lower() in selected_level.lower():
                        selected_level = level
                        break
                else:
                    # If still not found, return middle level as fallback
                    selected_level = available_levels[len(available_levels) // 2] if available_levels else None
            
            # Cache the result
            if not hasattr(self, '_seniority_cache'):
                self._seniority_cache = {}
            self._seniority_cache[cache_key] = selected_level
            
            self._log(f"LLM selected seniority: {selected_level}")
            return selected_level
        
        except Exception as e:
            self._log_warning(f"LLM seniority selection failed: {type(e).__name__}: {str(e)}")
            return None
    
    def parse_with_llm_and_sftp(self, offer_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse offer using LLM with dynamic CV_Theque directory discovery."""
        try:
            self._log(f"===== Starting LLM+CV_Theque parsing =====")
            self._log(f"Offer text length: {len(offer_text)} characters")
            
            # Step 1: Get available profiles from CV_Theque
            self._log("Step 1: Getting available profiles from CV_Theque...")
            available_profiles = self._get_available_profiles()
            
            if not available_profiles:
                self._log_warning("No profiles available from CV_Theque, falling back to keyword detection")
                return self.parse_with_keywords(offer_text)
            
            # Step 2: Use LLM to select best profile
            self._log(f"Step 2: Using LLM to select best profile from {len(available_profiles)} options")
            profile = self._select_profile_with_llm(offer_text, available_profiles)
            
            if not profile:
                self._log_warning("LLM profile selection failed, falling back to keyword detection")
                return self.parse_with_keywords(offer_text)
            
            # Step 3: Get available seniority levels for selected profile
            self._log(f"Step 3: Getting available seniority levels for profile '{profile}'...")
            available_levels = self._get_available_seniority_levels(profile)
            
            if not available_levels:
                self._log_warning(f"No seniority levels available for {profile}, using default")
                return profile, "Junior"
            
            # Step 4: Use LLM to select best seniority level
            self._log(f"Step 4: Using LLM to select best seniority from {len(available_levels)} options")
            seniority = self._select_seniority_with_llm(offer_text, available_levels)
            
            if not seniority:
                self._log_warning("LLM seniority selection failed, using default")
                return profile, "Junior"
            
            # Step 5: Double-check the selection
            self._log("Step 5: Double-checking selections...")
            if profile not in available_profiles:
                self._log_error(f"Double-check failed: profile '{profile}' not in available_profiles")
                return available_profiles[0], seniority if seniority in available_levels else available_levels[0]
            
            if seniority not in available_levels:
                self._log_error(f"Double-check failed: seniority '{seniority}' not in available levels")
                return profile, available_levels[0]
            
            self._log(f"===== LLM+CV_Theque parsing successful =====")
            self._log(f"Seniority via LLM selection → {seniority}")
            self._log(f"Final result: profile={profile}, seniority={seniority}")
            return profile, seniority
        
        except Exception as e:
            self._log_error(f"LLM+CV_Theque parsing failed: {str(e)}")
            return self.parse_with_keywords(offer_text)
    
    def parse_with_keywords(self, offer_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse offer using keyword-based detection (fallback)."""
        text_lower = offer_text.lower()
        
        # Detect profile
        detected_profile = None
        best_score = 0
        
        for profile, keywords in PROFILES.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > best_score:
                best_score = score
                detected_profile = profile
        
        # Detect seniority — year-based parsing first (avoids substring false positives)
        detected_seniority = None
        min_years = _extract_min_experience_years(offer_text)
        if min_years is not None:
            detected_seniority = _seniority_from_years(min_years)
            self._log(
                f"Seniority via year parsing ({min_years} ans minimum) → {detected_seniority}"
            )
        else:
            best_seniority_score = 0
            for seniority, keywords in SENIORITY_LEVELS.items():
                score = sum(1 for keyword in keywords if keyword in text_lower)
                if score > best_seniority_score:
                    best_seniority_score = score
                    detected_seniority = seniority
            self._log(
                f"Seniority via keyword matching (score={best_seniority_score}) → {detected_seniority}"
            )

        self._log(f"Keyword parsing result: profile={detected_profile}, seniority={detected_seniority}")
        return detected_profile, detected_seniority
    
    def parse_offer(self, file_path: Path, use_llm: bool = True) -> Tuple[str, str]:
        """
        Parse job offer file and extract profile and seniority.
        
        Args:
            file_path: Path to job offer file
            use_llm: Whether to use LLM parsing (falls back to keywords if fails)
        
        Returns:
            Tuple of (profile, seniority)
        
        Raises:
            ValueError: If parsing fails completely
        """
        try:
            # Extract text from file
            offer_text = self.extract_text_from_file(file_path)
            
            if not offer_text.strip():
                raise ValueError("No text extracted from offer file")
            
            # Parse with LLM and SFTP (optimized with caching)
            if use_llm:
                profile, seniority = self.parse_with_llm_and_sftp(offer_text)
            else:
                profile, seniority = self.parse_with_keywords(offer_text)
            
            # Validate results
            if not profile:
                app_logger.warning("Could not detect profile, using default")
                profile = "fullstack"
            
            if not seniority:
                app_logger.warning("Could not detect seniority, using default")
                seniority = "junior"
            
            app_logger.info(f"Offer parsing successful: profile={profile}, seniority={seniority}")
            return profile, seniority
        
        except Exception as e:
            app_logger.error(f"Offer parsing failed: {str(e)}")
            # Return defaults on failure
            return "fullstack", "junior"


    def extract_offer_metadata(self, text: str) -> dict:
        """Extract structured offer metadata from raw text using LLM.

        Returns a dict with keys: title, description, skills,
        experience_level, location, salary_range.
        Returns an empty dict (not an exception) on any failure — the caller
        must be able to create an offer even if extraction fails.
        """
        if not text or not text.strip():
            return {}

        max_chars = CONFIG.get("extraction", {}).get("max_prompt_chars", 3000)
        skills_rules = (METADATA_SKILLS_RULES or "").strip()
        skills_schema = skills_rules or '"skills": ["compétence1", "compétence2"],'

        system_prompt = (
            "Tu es un expert en analyse de fiches de poste. "
            "Extrais les informations clés et retourne UNIQUEMENT un objet JSON valide, "
            "sans aucun texte avant ou après le JSON."
        )
        user_prompt = (
            "Analyse cette fiche de poste et extrais les informations suivantes en JSON :\n\n"
            "{\n"
            '  "title": "Titre exact du poste",\n'
            '  "description": "Résumé du poste en 2-3 phrases",\n'
            f"  {skills_schema}\n"
            '  "experience_level": "Junior|Confirmé|Senior|Expert (null si non mentionné). '
            "Barèmes : 0-2 ans → Junior, 3-5 ans → Confirmé, 6-10 ans → Senior, 11+ ans → Expert. "
            'Ex. « 3+ ans minimum » → Confirmé, « 2 à 5 ans » → Confirmé (utiliser le plafond de la fourchette)",\n'
            '  "contract_type": "CDI|CDD|Freelance|Stage|Alternance|Regie (CDI par défaut si non mentionné). '
            "Règles : CDD = contrat à durée déterminée/temporaire ; Freelance = freelance/indépendant/mission ; "
            'Stage = stage/stagiaire ; Alternance = alternance/apprentissage ; Regie = régie/prestation",\n'
            '  "location": "Lieu ou null",\n'
            '  "salary_range": "Fourchette salariale ou null"\n'
            "}\n\n"
            f"Fiche de poste :\n{text[:max_chars]}\n\n"
            "Réponds UNIQUEMENT avec le JSON."
        )

        try:
            raw = self._call_llm_with_fallback(system_prompt, user_prompt)
            raw = raw.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`").strip()
            data = json.loads(raw)
        except Exception as exc:
            app_logger.warning(f"Offer metadata extraction failed: {exc}")
            return {}

        def _clean(v: object) -> Optional[str]:
            s = str(v).strip() if v is not None else ""
            return None if s in ("", "null", "None", "undefined") else s

        experience_level = _clean(data.get("experience_level"))
        experience_years = _extract_min_experience_years(text)
        if experience_years is not None:
            experience_level = _seniority_display_label(_seniority_from_years(experience_years))
            app_logger.info(
                f"experience_level overridden via year parsing ({experience_years} ans) → {experience_level}"
            )

        min_years, max_years = _extract_experience_range(text)
        contract_type = _detect_contract_type(text, _clean(data.get("contract_type")))

        skills = data.get("skills") if isinstance(data.get("skills"), list) else []
        skills = [s.strip() for s in skills if isinstance(s, str) and s.strip()][:15]

        return {
            "title": _clean(data.get("title")),
            "description": _clean(data.get("description")),
            "skills": skills,
            "experience_level": experience_level,
            "experience_min_years": min_years,
            "experience_max_years": max_years,
            "contract_type": contract_type,
            "location": _clean(data.get("location")),
            "salary_range": _clean(data.get("salary_range")),
        }


def get_offer_parser(stdout_log: Optional[Path] = None, stderr_log: Optional[Path] = None) -> OfferParser:
    """Create offer parser instance."""
    return OfferParser(stdout_log=stdout_log, stderr_log=stderr_log)
