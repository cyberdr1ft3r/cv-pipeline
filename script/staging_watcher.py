"""
Local Staging Folder Watcher â€” script/staging_watcher.py

Long-running daemon that:
  1. Polls a local staging folder for new CV files (PDF / DOCX / DOC)
  2. Extracts each CV via the same logic as script/01_extraction_and_validation.py
  3. Classifies profile/seniority (keyword-first â†’ LLM fallback)
  4. Routes extracted JSON + original file to
       CV_Theque/{profile}/{seniority}/extracted/   and
       CV_Theque/{profile}/{seniority}/originals/
  5. Moves the staging file to staging/processed/ on success,
     staging/failed/ on unrecoverable failure

Usage:
    python script/staging_watcher.py
    python -m script.staging_watcher

Environment variables (all loaded via service.config â†’ config/.env):
    CV_LIBRARY_ROOT      â€” CV_Theque root (default /sftp/cv_tech/files/CV_Theque)
    WATCHER_STAGING_PATH        (default /sftp/cv_tech/files/staging)
    WATCHER_POLL_INTERVAL_SECONDS (default 30)
    WATCHER_MAX_WORKERS         (default 4)
    OPENROUTER_API_KEY
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import unicodedata
import time
import zipfile
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree

# â”€â”€â”€ Bootstrap: trigger env loading chain (same as rest of monolith) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Must come before any os.getenv() calls.
import service.config  # noqa: F401

from service.cv_storage import LocalCVStorage, normalize_profile, normalize_seniority

try:
    from script.experience_years import enrich_annees_experience
except ImportError:
    from experience_years import enrich_annees_experience

import yaml
from openai import OpenAI

# â”€â”€â”€ Project paths & YAML config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config_yaml.yaml"

with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CONFIG = yaml.safe_load(_f)

# â”€â”€â”€ Logger (standalone format â€” not JSON like the API service) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Level driven by config logging.level; default INFO.
_log_level = getattr(logging, _CONFIG.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("staging_watcher")

# â”€â”€â”€ Watcher configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CV_STORAGE_ROOT = os.getenv("CV_STORAGE_ROOT", "/sftp/cv_tech/files")
CV_LIBRARY_ROOT = os.getenv("CV_LIBRARY_ROOT", "/sftp/cv_tech/files/CV_Theque")
WATCHER_STAGING_PATH = os.getenv("WATCHER_STAGING_PATH", "/sftp/cv_tech/files/staging")
WATCHER_POLL_INTERVAL = int(os.getenv("WATCHER_POLL_INTERVAL_SECONDS", "30"))
WATCHER_MAX_WORKERS = int(os.getenv("WATCHER_MAX_WORKERS", "4"))

_SUPPORTED_EXTENSIONS = set(_CONFIG["pipeline"]["supported_extensions"])
_SKIP_DIR_NAMES = set(_CONFIG["watcher"]["reserved_dir_names"])

# â”€â”€â”€ LLM client (one shared instance â€” thread-safe for reads) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
_llm_client = OpenAI(
    base_url=_CONFIG["api"]["base_url"],
    api_key=_OPENROUTER_API_KEY,
)

# â”€â”€â”€ Prompt templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _load_prompt(key: str) -> str:
    rel = _CONFIG["prompts"][key]
    return (_PROJECT_ROOT / "config" / rel).read_text(encoding="utf-8")


_EXTRACTION_PROMPT = _load_prompt("extraction")
_VALIDATION_PROMPT = _load_prompt("validation")
_PROFILE_SYSTEM = _load_prompt("offer_parser_profile_system")
_PROFILE_USER_TMPL = _load_prompt("offer_parser_profile_user")
_SENIORITY_SYSTEM = _load_prompt("offer_parser_seniority_system")
_SENIORITY_USER_TMPL = _load_prompt("offer_parser_seniority_user")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

StagedFile = namedtuple(
    "StagedFile",
    ["path", "filename", "profile_hint", "seniority_hint"],
)
# path:           full local filesystem path (used as in-flight key)
# filename:       basename (e.g. "john_doe.pdf")
# profile_hint:   profile from staging path or None
# seniority_hint: seniority from staging path or None


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Text extraction helpers  (same logic as 01_extraction_and_validation.py)
# Note: cannot import from that module â€” module-level side effects (load_dotenv,
# FileNotFoundError guard, RuntimeError guard) make direct import unsafe.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _extract_text_pdf(path: str) -> str:
    """Extract text from PDF: pdfplumber â†’ pypdf â†’ OCR fallback."""
    import pdfplumber
    from pypdf import PdfReader

    text = ""

    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text.strip() + "\n\n"
    except Exception as exc:
        logger.warning("[Extract] pdfplumber failed: %s", exc)

    if len(text.strip()) < 100:
        try:
            reader = PdfReader(path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text.strip() + "\n\n"
        except Exception as exc:
            logger.warning("[Extract] pypdf failed: %s", exc)

    if len(text.strip()) < 100:
        logger.info("[Extract] Activating OCR for scanned PDF: %s", Path(path).name)
        try:
            from pdf2image import convert_from_path
            import pytesseract

            poppler_path = _CONFIG["paths"].get("POPPLER_PATH") or None
            if poppler_path and not Path(poppler_path).exists():
                poppler_path = None  # Fall back to PATH lookup on non-Windows

            images = convert_from_path(path, dpi=_CONFIG["extraction"]["ocr_dpi"], poppler_path=poppler_path)
            for img in images:
                text += pytesseract.image_to_string(img, lang="fra+eng") + "\n\n"
        except Exception as exc:
            logger.error("[Extract] OCR failed: %s", exc)

    return text.strip()


_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WORD_PARAGRAPH = f"{{{_WORD_NAMESPACE}}}p"
_WORD_TEXT = f"{{{_WORD_NAMESPACE}}}t"
_WORD_TAB = f"{{{_WORD_NAMESPACE}}}tab"
_WORD_BREAKS = {
    f"{{{_WORD_NAMESPACE}}}br",
    f"{{{_WORD_NAMESPACE}}}cr",
}


class UnsupportedLegacyDocError(ValueError):
    """Raised when the watcher receives a legacy binary Word document."""


def _normalize_extracted_text(text: str) -> str:
    """Normalize whitespace while retaining useful paragraph boundaries."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _extract_docx_xml_part(xml_data: bytes) -> List[str]:
    """Return each Word paragraph once, including paragraphs nested in textboxes."""
    root = ElementTree.fromstring(xml_data)
    parent_by_child = {
        child: parent
        for parent in root.iter()
        for child in parent
    }
    paragraphs: List[str] = []

    for paragraph in root.iter(_WORD_PARAGRAPH):
        fragments: List[str] = []
        for node in paragraph.iter():
            if node is paragraph:
                continue

            ancestor = parent_by_child.get(node)
            while ancestor is not None and ancestor.tag != _WORD_PARAGRAPH:
                ancestor = parent_by_child.get(ancestor)
            if ancestor is not paragraph:
                # A nested w:p (for example, w:txbxContent) is emitted by its
                # own iteration. Excluding it here avoids duplicate textbox text.
                continue

            if node.tag == _WORD_TEXT and node.text:
                fragments.append(node.text)
            elif node.tag == _WORD_TAB:
                fragments.append("\t")
            elif node.tag in _WORD_BREAKS:
                fragments.append("\n")

        normalized = _normalize_extracted_text("".join(fragments))
        if normalized:
            paragraphs.append(normalized)

    return paragraphs


def _extract_text_docx(path: str) -> str:
    """Extract DOCX body, textbox, header, and footer text from Word XML."""
    source = Path(path)
    if source.suffix.lower() == ".doc":
        raise UnsupportedLegacyDocError(
            "unsupported legacy .doc format; conversion to .docx is required"
        )

    try:
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            part_names = ["word/document.xml"]
            part_names.extend(
                sorted(
                    name
                    for name in names
                    if name.startswith("word/header") and name.endswith(".xml")
                )
            )
            part_names.extend(
                sorted(
                    name
                    for name in names
                    if name.startswith("word/footer") and name.endswith(".xml")
                )
            )
            paragraphs = [
                paragraph
                for part_name in part_names
                for paragraph in _extract_docx_xml_part(archive.read(part_name))
            ]
    except (KeyError, OSError, ElementTree.ParseError, zipfile.BadZipFile) as exc:
        logger.warning(
            "[Extract] Direct DOCX XML extraction failed for %s; using python-docx fallback: %s",
            source.name,
            exc,
        )
        from docx import Document

        doc = Document(source)
        paragraphs = [paragraph.text for paragraph in doc.paragraphs]

    return _normalize_extracted_text("\n\n".join(paragraphs))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# JSON cleaning helpers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _fix_json(text: str) -> str:
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    text = re.sub(r'"\s*\n\s*"', '",\n"', text)
    text = re.sub(r'"\s*\n\s*"([^"]+)"\s*:', '",\n"\\1":', text)
    return text.lstrip("ï»¿\x00")


def _clean_json(text: str) -> Optional[str]:
    if not text:
        return None
    if "```" in text:
        for part in text.split("```"):
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
    return _fix_json(text[start : end + 1].strip())


def _repair_json(text: str) -> Optional[Dict]:
    cleaned = _clean_json(text) or text.strip()
    if not cleaned:
        return None
    try:
        return json.loads(_fix_json(cleaned))
    except json.JSONDecodeError:
        pass

    truncated = _truncate_repair_json_text(cleaned)
    if truncated:
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    try:
        lines = cleaned.split("\n")
        depth, json_lines, started = 0, [], False
        for line in lines:
            if "{" in line and not started:
                started = True
            if started:
                json_lines.append(line)
                depth += line.count("{") - line.count("}")
                if depth == 0:
                    break
        if json_lines:
            block = _fix_json("\n".join(json_lines))
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                truncated = _truncate_repair_json_text(block)
                if truncated:
                    return json.loads(truncated)
    except Exception:
        pass
    return None


def _truncate_repair_json_text(json_text: str) -> Optional[str]:
    """Close truncated JSON at the last complete object/array entry."""
    try:
        json.loads(json_text)
        return json_text
    except json.JSONDecodeError as exc:
        error_pos = exc.pos
        truncated = json_text[:error_pos]
        last_complete = max(truncated.rfind("},"), truncated.rfind("}"))
        if last_complete > 0:
            candidate = truncated[: last_complete + 1]
            open_braces = candidate.count("{") - candidate.count("}")
            open_brackets = candidate.count("[") - candidate.count("]")
            candidate += "]" * open_brackets + "}" * open_braces
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        last_good = truncated.rfind('"},')
        if last_good == -1:
            last_good = truncated.rfind('"}')
        if last_good > 0:
            candidate = truncated[: last_good + 2]
            open_braces = candidate.count("{") - candidate.count("}")
            candidate += "}" * open_braces
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
    return None


def _parse_llm_json(raw: str) -> Dict:
    cleaned = _clean_json(raw)
    if cleaned:
        try:
            return json.loads(_fix_json(cleaned))
        except json.JSONDecodeError:
            truncated = _truncate_repair_json_text(_fix_json(cleaned))
            if truncated:
                try:
                    return json.loads(truncated)
                except json.JSONDecodeError:
                    pass
    repaired = _repair_json(raw)
    if repaired:
        return repaired
    raise ValueError("Could not parse LLM JSON response after cleaning and repair")


def _validation_prompt(cv_text: str, broken_json: str) -> str:
    max_chars = _CONFIG.get("extraction", {}).get("max_prompt_chars", 3000)
    preview = (broken_json or "")[:2000]
    safe_cv = cv_text[:max_chars].replace("{", "{{").replace("}", "}}")
    safe_preview = preview.replace("{", "{{").replace("}", "}}")
    return _VALIDATION_PROMPT.format(cv_text=safe_cv, json_preview=safe_preview)


def _extract_cv_json(cv_text: str) -> Dict:
    """LLM extraction with validation repair when JSON parsing fails."""
    prompt = _EXTRACTION_PROMPT.format(cv_text=cv_text)
    raw_response = _call_llm(prompt, reject_truncated=True)
    if not raw_response:
        raise RuntimeError("LLM extraction returned no response")

    try:
        return _parse_llm_json(raw_response)
    except ValueError:
        logger.warning(
            "[Processor] Initial JSON parse failed (response=%d chars), requesting validation repair",
            len(raw_response),
        )

    validated_raw = _call_llm(
        _validation_prompt(cv_text, raw_response),
        reject_truncated=True,
    )
    if not validated_raw:
        raise ValueError("Could not parse LLM JSON response after cleaning and repair")

    try:
        return _parse_llm_json(validated_raw)
    except ValueError:
        logger.warning(
            "[Processor] Validation JSON parse failed (response=%d chars)",
            len(validated_raw),
        )
        raise ValueError("Could not parse LLM JSON response after cleaning and repair")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# LLM helper
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    use_fallback: bool = True,
    reject_truncated: bool = False,
) -> Optional[str]:
    """Call OpenRouter with retry and fallback models."""
    primary = _CONFIG["api"]["model"]
    models = [primary]
    if use_fallback:
        models.extend(_CONFIG["api"].get("fallback_models", []))

    retries = _CONFIG["api"].get("max_retries", 5)
    wait = _CONFIG["api"].get("retry_wait_seconds", 10)

    messages: List[Dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for model_idx, model in enumerate(models):
        for attempt in range(retries):
            try:
                response = _llm_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=_CONFIG["api"]["temperature"],
                    max_tokens=_CONFIG["api"]["max_tokens"],
                )
                choice = response.choices[0]
                if reject_truncated and choice.finish_reason == "length":
                    logger.error(
                        "[LLM] Rejected truncated response: model=%s attempt=%d/%d finish_reason=%s",
                        model,
                        attempt + 1,
                        retries,
                        choice.finish_reason,
                    )
                    return None
                return choice.message.content
            except Exception as exc:
                logger.warning(
                    "[LLM] Attempt %d/%d with %s failed: %s",
                    attempt + 1, retries, model, exc,
                )
                time.sleep(wait * (attempt + 1))
        if model_idx < len(models) - 1:
            logger.info("[LLM] Switching to fallback: %s", models[model_idx + 1])

    logger.error("[LLM] All models exhausted")
    return None


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# JSON normalizer  (simplified validate_and_enrich_json)
# Full version in 01_extraction_and_validation.py cannot be imported due to
# module-level side effects. This version ensures required keys exist and
# handles the most common LLM structural variants.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _validate_json(data: Dict) -> Dict:
    # Normalize alternate key names LLMs sometimes emit
    if "experiences" in data and "experiences_professionnelles" not in data:
        data["experiences_professionnelles"] = data.pop("experiences")

    # Ensure required top-level keys with safe defaults
    ip = data.setdefault("informations_personnelles", {})
    ip.setdefault("nom_complet", "")
    ip.setdefault("titre", "")

    data.setdefault("experiences_professionnelles", [])
    data.setdefault("competences", {"methodologies_et_outils": [], "technologies": []})
    data.setdefault("formation", [])
    data.setdefault("certifications", [])
    data.setdefault("projets_realises", [])
    data.setdefault("langues", [])
    data.setdefault("profil_resume", {"description": "", "annees_experience": "", "specialisations": []})

    enrich_annees_experience(data)
    return data


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Classification
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class ClassificationError(Exception):
    pass


_KNOWN_SENIORITIES = set(_CONFIG["pipeline"]["seniority_levels"])

# Ordered keyword â†’ profile (longest first to avoid partial clashes)
_PROFILE_KEYWORDS: List[Tuple[str, str]] = sorted(
    [
        ("full stack", "FullStack"),
        ("fullstack", "FullStack"),
        ("full-stack", "FullStack"),
        ("data analyst", "Data_Analyst"),
        ("data scientist", "Data_Scientist"),
        ("data engineer", "Data_Engineer"),
        ("devops", "DevOps"),
        ("dev ops", "DevOps"),
        ("product manager", "Product_Manager"),
        ("scrum master", "Scrum_Master"),
        ("project manager", "Project_Manager"),
        ("quality assurance", "QA"),
        ("backend", "Backend"),
        ("back-end", "Backend"),
        ("back end", "Backend"),
        ("frontend", "Frontend"),
        ("front-end", "Frontend"),
        ("front end", "Frontend"),
        ("mobile", "Mobile"),
        (" qa ", "QA"),
        # Business Analyst â€” checked before generic "analyst" entries
        ("chef de projet fonctionnel", "BusinessAnalyst"),
        ("maÃ®trise d'ouvrage", "BusinessAnalyst"),
        ("maitrise d'ouvrage", "BusinessAnalyst"),
        ("analyse fonctionnelle", "BusinessAnalyst"),
        ("functional analyst", "BusinessAnalyst"),
        ("business analyst", "BusinessAnalyst"),
        ("business-analyst", "BusinessAnalyst"),
        (" moa ", "BusinessAnalyst"),
    ],
    key=lambda x: len(x[0]),
    reverse=True,
)

# Ordered (keyword, seniority) â€” highest seniority checked first
_SENIORITY_CHECKS: List[Tuple[str, str]] = [
    ("tech lead", "Expert"),
    ("architecte", "Expert"),
    ("architect", "Expert"),
    ("expert", "Expert"),
    ("senior", "Senior"),
    ("confirmÃ©e", "Confirme"),
    ("confirmÃ©", "Confirme"),
    ("confirme", "Confirme"),
    ("confirmed", "Confirme"),
    ("intermÃ©diaire", "Confirme"),
    ("intermediaire", "Confirme"),
    ("junior", "Junior"),
    ("dÃ©butant", "Junior"),
    ("debutant", "Junior"),
    ("stagiaire", "Junior"),
]


def _get_cv_title(extracted: Dict) -> str:
    """Return the best available title string from an extracted CV JSON."""
    title = extracted.get("informations_personnelles", {}).get("titre", "")
    if not title:
        title = extracted.get("titre", "")
    if not title:
        exps = extracted.get("experiences_professionnelles", [])
        if exps:
            title = exps[0].get("titre_poste", "")
    return title or ""


def _keyword_match_profile(title: str) -> Optional[str]:
    lower = f" {title.lower()} "  # pad to help boundary checks like " qa "
    for keyword, profile in _PROFILE_KEYWORDS:
        if keyword in lower:
            return profile
    return None


def _keyword_match_seniority(title: str) -> Optional[str]:
    lower = title.lower()
    for keyword, seniority in _SENIORITY_CHECKS:
        if keyword in lower:
            return seniority
    return None


def _seniority_from_years(annees_experience: str) -> Optional[str]:
    """
    Map annees_experience ('5 ans', '5+ ans', '10 ans') to a seniority level.
    Used as a reliable fallback when the titre field has been LLM-normalized
    and seniority keywords were stripped or translated (e.g. 'confirmÃ©' â†’ 'Senior').

    French consulting market thresholds (IT Road convention):
      0â€“2 ans  â†’ Junior
      3â€“5 ans  â†’ Confirme
      6â€“10 ans â†’ Senior
      11+ ans  â†’ Expert
    """
    if not annees_experience:
        return None
    m = re.search(r"(\d+)", annees_experience)
    if not m:
        return None
    years = int(m.group(1))
    if years <= 2:
        return "Junior"
    if years <= 5:
        return "Confirme"
    if years <= 10:
        return "Senior"
    return "Expert"


_SENIORITY_RANK: Dict[str, int] = {
    "Junior": 0,
    "Confirme": 1,
    "Senior": 2,
    "Expert": 3,
}


def _higher_seniority(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Return the higher of two seniority levels (by IT Road rank)."""
    if not a:
        return b
    if not b:
        return a
    rank_a = _SENIORITY_RANK.get(a, -1)
    rank_b = _SENIORITY_RANK.get(b, -1)
    return a if rank_a >= rank_b else b


def _normalize_profile_name(raw: str) -> str:
    """
    Normalize an LLM-suggested profile name to the project naming convention.

    Examples:
      "human resources"     -> "Human_Resources"
      "Ressources Humaines" -> "Ressources_Humaines"
      "HR"                  -> "HR"   (short all-caps acronym preserved)
      "data analyst"        -> "Data_Analyst"
    """
    if not raw or not raw.strip():
        return ""
    # Decompose unicode and drop non-ASCII (handles e->e, a->a, c->c, etc.)
    nfkd = unicodedata.normalize("NFKD", raw.strip())
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    # Keep only letters, digits, spaces; replace everything else with a space
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", " ", ascii_str)
    # Collapse runs of whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    parts = []
    for word in cleaned.split():
        # Short all-caps words are acronyms -- preserve casing (HR, QA, MOA, RH)
        if word.isupper() and len(word) <= 4:
            parts.append(word)
        else:
            parts.append(word.capitalize())
    return "_".join(parts)


def _discover_profiles(storage: LocalCVStorage) -> frozenset:
    """
    Read the CV_Theque root directory and return the set of existing profile folder names.

    Called once per poll cycle by WatcherDaemon._poll(). Returns an empty frozenset
    on filesystem error so classification can still proceed (LLM has no anchor list but
    can still suggest a new name).
    """
    try:
        root = storage.resolve(CV_LIBRARY_ROOT)
        profiles = frozenset(p.name for p in root.iterdir() if p.is_dir())
        logger.debug("[Profiles] Discovered %d profiles: %s", len(profiles), sorted(profiles))
        return profiles
    except Exception as exc:
        logger.warning("[Profiles] Could not read CV_Theque profiles: %s -- proceeding without anchor list", exc)
        return frozenset()


def _resolve_profile(
    extracted: Dict,
    hint: Optional[str],
    known_profiles: frozenset,
    pending_profiles: Dict,
    pending_lock: threading.Lock,
) -> str:
    """
    Resolve the profile for a CV using a 4-step cascade:
      0. Staging path hint (always trusted)
      1. Keyword match against _PROFILE_KEYWORDS (fast path for known IT profiles)
      2. LLM with live known_profiles list (may suggest a new profile name)
      3. Normalize LLM output, register in pending_profiles to prevent naming divergence
    """
    if hint:
        return hint

    title = _get_cv_title(extracted)

    # Step 1: keyword match â€” fast, no LLM call needed for common IT profiles
    matched = _keyword_match_profile(title)
    if matched:
        return matched

    # Step 2: LLM with live profile list
    # Fallback seed list used when SFTP discovery failed (known_profiles is empty)
    _SEED = "Backend, BusinessAnalyst, Data_Analyst, Data_Scientist, Data_Engineer, DevOps, Frontend, FullStack, Mobile, Product_Manager, Project_Manager, QA, Scrum_Master"
    profiles_list = ", ".join(sorted(known_profiles)) if known_profiles else _SEED
    prompt = _PROFILE_USER_TMPL.format(profiles=profiles_list, offer_text=title)
    response = _call_llm(prompt, system_prompt=_PROFILE_SYSTEM, use_fallback=False)

    if not response or not response.strip():
        raise ClassificationError(f"LLM returned no profile for title: {title!r}")

    raw = response.strip()

    # Case-insensitive match against known profiles first (LLM may return wrong case)
    raw_lower = raw.lower()
    for known in known_profiles:
        if known.lower() == raw_lower:
            return known

    # LLM suggested a new profile â€” normalize to naming convention
    normalized = _normalize_profile_name(raw)
    if not normalized:
        raise ClassificationError(f"LLM returned unrecognizable profile name {raw!r} for title: {title!r}")

    # Register in pending_profiles so concurrent workers reuse the same name
    norm_key = normalized.lower()
    with pending_lock:
        if norm_key in pending_profiles:
            return pending_profiles[norm_key]
        pending_profiles[norm_key] = normalized

    logger.info("[Classify] New profile %r will be created for title=%r", normalized, title)
    return normalized


_INTERNSHIP_TYPES = set(_CONFIG["watcher"]["internship_contract_types"])


def _all_internships(extracted: Dict) -> bool:
    """Return True if every experience entry has a type_contrat that is an internship type."""
    exps = extracted.get("experiences_professionnelles", [])
    if not exps:
        return False
    return all(
        exp.get("type_contrat", "").lower().strip() in _INTERNSHIP_TYPES
        for exp in exps
    )


def _resolve_seniority(extracted: Dict, hint: Optional[str]) -> str:
    title = _get_cv_title(extracted)
    profil = extracted.get("profil_resume", {})
    annees = profil.get("annees_experience", "")

    # Diagnostic: log what signals are available (helps trace LLM normalization issues)
    logger.debug(
        "[Classify] seniority signals â€” titre=%r annees_experience=%r hint=%r",
        title, annees, hint,
    )

    # Step 0: internship override â€” if every experience is Stage/PFE/Alternance/
    # Apprentissage/Contrat Pro, this is a fresh graduate regardless of what the
    # titre or annees_experience says. Return Junior unconditionally.
    if _all_internships(extracted):
        logger.info("[Classify] All experiences are internships â†’ Junior (Step 0 override)")
        return "Junior"

    # Step 1: keyword match on titre (may fail if LLM translated 'confirmÃ©' â†’ 'Senior'
    # or stripped it; steps 2â€“4 defend against that)
    years_level = _seniority_from_years(annees)
    text_level: Optional[str] = _keyword_match_seniority(title)

    # Step 2: keyword match on profil_resume.specialisations
    if not text_level:
        specialisations = profil.get("specialisations", [])
        if isinstance(specialisations, list) and specialisations:
            spec_text = " ".join(str(s) for s in specialisations)
            matched = _keyword_match_seniority(spec_text)
            if matched:
                logger.info("[Classify] Seniority from specialisations=%r â†’ %s", spec_text, matched)
                text_level = matched

    # Step 3: LLM fallback when titre/spec keywords miss
    if not text_level:
        levels_list = ", ".join(sorted(_KNOWN_SENIORITIES))
        prompt = _SENIORITY_USER_TMPL.format(levels=levels_list, offer_text=title)
        response = _call_llm(prompt, system_prompt=_SENIORITY_SYSTEM, use_fallback=False)
        if response:
            candidate = normalize_seniority(response.strip())
            if candidate in _KNOWN_SENIORITIES:
                text_level = candidate

    # Step 4: annees_experience is authoritative when present (IT Road thresholds).
    # Title/path hints may say "Senior" for 3â€“5 ans profiles â€” years wins both ways.
    if years_level:
        text_or_hint = _higher_seniority(text_level, hint)
        if text_or_hint and text_or_hint != years_level:
            logger.info(
                "[Classify] Seniority from annees_experience=%r overrides %s â†’ %s",
                annees, text_or_hint, years_level,
            )
        else:
            logger.info("[Classify] Seniority from annees_experience=%r â†’ %s", annees, years_level)
        return years_level

    # No years signal â€” fall back to text keyword, path hint, or LLM text_level.
    baseline = _higher_seniority(hint, text_level) if hint else text_level
    if baseline:
        return baseline

    raise ClassificationError(f"seniority uncertain for title: {title!r}")


def _classify(
    extracted: Dict,
    profile_hint: Optional[str],
    seniority_hint: Optional[str],
    known_profiles: frozenset,
    pending_profiles: Dict,
    pending_lock: threading.Lock,
) -> Tuple[str, str]:
    """
    Return (profile, seniority).
    Raises ClassificationError if either cannot be determined confidently.
    """
    profile = _resolve_profile(extracted, profile_hint, known_profiles, pending_profiles, pending_lock)
    seniority = _resolve_seniority(extracted, seniority_hint)
    return profile, seniority


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# StagingScanner
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class StagingScanner:
    """Walks the local staging tree and returns discovered CV files."""

    def __init__(self, storage: LocalCVStorage, staging_path: str) -> None:
        self._storage = storage
        self._staging_path = Path(staging_path)

    def scan(self) -> List[StagedFile]:
        results: List[StagedFile] = []
        staging_root = self._storage.resolve(self._staging_path)
        if not staging_root.exists():
            logger.warning("[Scanner] Staging path not found: %s", staging_root)
            return results

        for path in sorted(staging_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue
            rel = path.relative_to(staging_root)
            parts_lower = [part.lower() for part in rel.parts]
            if any(part in _SKIP_DIR_NAMES for part in parts_lower[:-1]):
                continue
            profile_hint = normalize_profile(rel.parts[0]) if len(rel.parts) >= 2 else None
            seniority_hint = None
            if len(rel.parts) >= 3:
                maybe_seniority = normalize_seniority(rel.parts[1])
                if maybe_seniority in _KNOWN_SENIORITIES:
                    seniority_hint = maybe_seniority
                else:
                    logger.warning("[Scanner] Unknown seniority directory '%s' in %s -- ignoring hint", rel.parts[1], path)
            results.append(StagedFile(str(path), path.name, profile_hint, seniority_hint))
        return results


class CVProcessor:
    """Handles end-to-end processing of a single staged CV file."""

    def __init__(self, storage: LocalCVStorage) -> None:
        self._storage = storage

    def process(
        self,
        staged: StagedFile,
        known_profiles: frozenset,
        pending_profiles: Dict,
        pending_lock: threading.Lock,
    ) -> None:
        """Process one staged file. Never raises; failures route to staging/failed/."""
        local_file = Path(staged.path)
        relative = _relative_path(staged)

        try:
            logger.info("[Processor] Processing local staged file %s", local_file)

            suffix = local_file.suffix.lower()
            if suffix == ".pdf":
                cv_text = _extract_text_pdf(str(local_file))
            elif suffix == ".docx":
                cv_text = _extract_text_docx(str(local_file))
            elif suffix == ".doc":
                raise UnsupportedLegacyDocError(
                    "unsupported legacy .doc format; original preserved for later conversion"
                )
            else:
                raise ValueError(f"Unsupported extension: {suffix}")

            if not cv_text or len(cv_text.strip()) < 100:
                raise ValueError("Extracted text is too short or empty")

            logger.info("[Processor] Extracted %d chars from %s", len(cv_text), staged.filename)
            extracted = _extract_cv_json(cv_text)
            extracted = _validate_json(extracted)

            logger.info(
                "[Processor] Extraction signals -- titre=%r annees_experience=%r",
                extracted.get("informations_personnelles", {}).get("titre", ""),
                extracted.get("profil_resume", {}).get("annees_experience", ""),
            )

            try:
                profile, seniority = _classify(
                    extracted,
                    staged.profile_hint,
                    staged.seniority_hint,
                    known_profiles,
                    pending_profiles,
                    pending_lock,
                )
            except ClassificationError as exc:
                logger.warning(
                    "[Processor] Classification failed for %s: %s -- routing to failed/",
                    staged.filename, exc,
                )
                _move_to_failed(self._storage, staged.path, relative, staged.filename)
                return

            logger.info("[Processor] Classified %s -> profile=%s seniority=%s", staged.filename, profile, seniority)

            stem = local_file.stem
            enrich_annees_experience(extracted)
            annees_written = extracted.get("profil_resume", {}).get("annees_experience", "")

            _cleanup_stale_cv_locations(self._storage, profile, seniority, stem, staged.filename)
            json_path = self._storage.store_extracted(profile, seniority, stem, extracted)
            orig_path = self._storage.store_original(local_file, profile, seniority)
            logger.info(
                "[Processor] Stored JSON=%s original=%s (annees_experience=%r)",
                json_path, orig_path, annees_written,
            )

            try:
                from service.candidate_store import upsert_candidate as _upsert_candidate
                candidate_id = _upsert_candidate(
                    cv_sftp_path=str(json_path),
                    profile=profile,
                    seniority=seniority,
                    extracted_json=extracted,
                )
                full_name = extracted.get("informations_personnelles", {}).get("nom_complet", staged.filename)
                logger.info("[Processor] Candidat %s enregistre en base (id=%s)", full_name, candidate_id)
            except Exception as db_exc:
                logger.warning("[Processor] Enregistrement candidat en base echoue pour %s: %s", staged.filename, db_exc)

            processed_path = Path(WATCHER_STAGING_PATH) / "processed" / relative
            self._storage.move(local_file, processed_path)
            logger.info("[Processor] Moved %s -> processed/%s", staged.filename, relative)

        except Exception as exc:
            logger.error("[Processor] Failed to process %s: %s", staged.filename, exc, exc_info=True)
            try:
                _move_to_failed(self._storage, staged.path, relative, staged.filename)
            except Exception as move_err:
                logger.error("[Processor] Could not move %s to failed/: %s", staged.filename, move_err)

def _relative_path(staged: StagedFile) -> str:
    """
    Compute the sub-path below the staging root, mirroring folder structure.
    Flat:    john_doe.pdf          â†’ john_doe.pdf
    Profile: FullStack/bob.pdf     â†’ FullStack/bob.pdf
    Both:    FullStack/Senior/a.pdf â†’ FullStack/Senior/a.pdf
    """
    try:
        return Path(staged.path).relative_to(Path(WATCHER_STAGING_PATH)).as_posix()
    except ValueError:
        return staged.filename


def _cleanup_stale_cv_locations(
    storage: LocalCVStorage,
    profile: str,
    seniority: str,
    stem: str,
    filename: str,
) -> None:
    """Remove duplicate JSON/original copies under other seniority folders for the same CV."""
    for other in _KNOWN_SENIORITIES:
        if other == seniority:
            continue
        stale_json = f"{CV_LIBRARY_ROOT}/{profile}/{other}/extracted/{stem}.json"
        stale_orig = f"{CV_LIBRARY_ROOT}/{profile}/{other}/originals/{filename}"
        try:
            storage.remove(stale_json)
            storage.remove(stale_orig)
        except Exception as exc:
            logger.warning(
                "[Processor] Could not remove stale copy under %s/%s: %s",
                profile, other, exc,
            )


def _move_to_failed(
    storage: LocalCVStorage,
    src_path: str,
    relative: str,
    filename: str,
) -> None:
    try:
        dst = Path(WATCHER_STAGING_PATH) / "failed" / relative
        storage.move(src_path, dst)
        logger.info("[Processor] Moved %s -> failed/%s", filename, relative)
    except Exception as exc:
        logger.error("[Processor] Could not move %s to failed/: %s", filename, exc)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# WatcherDaemon
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class WatcherDaemon:
    """
    Long-running poll loop with bounded concurrency and in-flight deduplication.

    Single instance only â€” in-memory in-flight set is sufficient.
    For multi-instance deployment, replace with Redis SET
    (see microservices architecture doc: 2026-05-17-microservices-architecture-design.md).
    """

    def __init__(self) -> None:
        self._in_flight: set[str] = set()
        self._in_flight_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._executor = ThreadPoolExecutor(
            max_workers=WATCHER_MAX_WORKERS, thread_name_prefix="watcher_worker"
        )

        self._storage = LocalCVStorage(
            storage_root=CV_STORAGE_ROOT,
            library_root=CV_LIBRARY_ROOT,
            staging_path=WATCHER_STAGING_PATH,
        )
        self._scanner = StagingScanner(self._storage, WATCHER_STAGING_PATH)
        self._processor = CVProcessor(self._storage)

    def run(self) -> None:
        logger.info(
            "[Daemon] Starting â€” poll=%ds workers=%d staging=%s cv_theque=%s",
            WATCHER_POLL_INTERVAL, WATCHER_MAX_WORKERS,
            WATCHER_STAGING_PATH, CV_LIBRARY_ROOT,
        )
        while not self._stop_event.is_set():
            self._poll()
            self._stop_event.wait(timeout=WATCHER_POLL_INTERVAL)

        logger.info("[Daemon] Stop event received â€” draining in-flight jobs...")
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("[Daemon] Shutdown complete")

    def stop(self) -> None:
        logger.info("[Daemon] Stopping...")
        self._stop_event.set()

    def _poll(self) -> None:
        # Discover current profiles from CV_Theque/ before scanning staging/
        known_profiles = _discover_profiles(self._storage)

        # Fresh pending dict per poll cycle â€” workers from this cycle share it
        pending_profiles: Dict = {}

        try:
            candidates = self._scanner.scan()
        except Exception as exc:
            logger.error("[Daemon] Scan error: %s", exc)
            return

        new_count = 0
        for staged in candidates:
            with self._in_flight_lock:
                if staged.path in self._in_flight:
                    continue
                self._in_flight.add(staged.path)

            future = self._executor.submit(
                self._processor.process,
                staged,
                known_profiles,
                pending_profiles,
                self._pending_lock,
            )
            future.add_done_callback(
                lambda _f, path=staged.path: self._release(path)
            )
            new_count += 1

        if candidates:
            logger.info(
                "[Daemon] Scan: %d found, %d submitted, %d already in-flight",
                len(candidates), new_count, len(candidates) - new_count,
            )

    def _release(self, path: str) -> None:
        with self._in_flight_lock:
            self._in_flight.discard(path)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Entry point
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def main() -> None:
    required = ("OPENROUTER_API_KEY",)
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error("[Watcher] Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    logger.info("[Watcher] Configuration:")
    logger.info("  Storage root:  %s", CV_STORAGE_ROOT)
    logger.info("  CV_Theque:     %s", CV_LIBRARY_ROOT)
    logger.info("  Staging:       %s", WATCHER_STAGING_PATH)
    logger.info("  Poll interval: %ds", WATCHER_POLL_INTERVAL)
    logger.info("  Max workers:   %d", WATCHER_MAX_WORKERS)

    daemon = WatcherDaemon()

    def _handle_signal(sig: int, _frame: object) -> None:
        logger.info("[Watcher] Signal %d received", sig)
        daemon.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    daemon.run()


if __name__ == "__main__":
    main()







