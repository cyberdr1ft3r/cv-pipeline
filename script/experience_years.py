"""Derive profil_resume.annees_experience from extracted professional experiences.

Used as a deterministic fallback when the LLM leaves annees_experience empty
despite having parseable experience dates (Action 277).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

INTERNSHIP_CONTRACT_TYPES = frozenset({
    "stage",
    "pfe",
    "alternance",
    "apprentissage",
    "contrat anapec",
    "contrat pro",
})

_INTERNSHIP_TITLE_HINTS = (
    "stagiaire",
    "(stage)",
    " stage",
    "stage)",
    "pfe",
    "alternance",
    "apprentissage",
)

_FRENCH_MONTHS: Dict[str, int] = {
    "janvier": 1,
    "janv": 1,
    "jan": 1,
    "fevrier": 2,
    "fevr": 2,
    "fev": 2,
    "mars": 3,
    "mar": 3,
    "avril": 4,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "jun": 6,
    "juillet": 7,
    "juil": 7,
    "jul": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "sep": 9,
    "sept": 9,
    "octobre": 10,
    "oct": 10,
    "novembre": 11,
    "nov": 11,
    "decembre": 12,
    "déc": 12,
    "dec": 12,
}

_PRESENT_MARKERS = (
    "present",
    "aujourdhui",
    "actuel",
    "en cours",
    "today",
    "now",
    "current",
)


def _ascii_lower(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _is_internship(exp: Dict) -> bool:
    contract = _ascii_lower(str(exp.get("type_contrat", "")).strip())
    if contract in INTERNSHIP_CONTRACT_TYPES:
        return True
    title = f" {_ascii_lower(str(exp.get('titre_poste', '')))} "
    if any(hint in title for hint in _INTERNSHIP_TITLE_HINTS):
        return True
    contexte = _ascii_lower(str(exp.get("contexte", "")))
    if re.search(r"\bstage\b", contexte):
        return True
    return any(
        marker in contexte
        for marker in (
            "projet fin d",
            "pfe",
            "alternance",
            "apprentissage",
            "observation",
        )
    )


def _parse_month_year(fragment: str) -> Optional[date]:
    fragment = fragment.strip()
    if not fragment:
        return None

    normalized = _ascii_lower(fragment)

    # Numeric month formats: 04/2022, 4-2022, 2022-04
    match = re.search(r"\b(0?[1-9]|1[0-2])[/.\-]((?:19|20)\d{2})\b", normalized)
    if match:
        return date(int(match.group(2)), int(match.group(1)), 1)
    match = re.search(r"\b((?:19|20)\d{2})[/.\-](0?[1-9]|1[0-2])\b", normalized)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)

    for month_name, month_num in sorted(_FRENCH_MONTHS.items(), key=lambda item: -len(item[0])):
        month_ascii = _ascii_lower(month_name)
        match = re.search(
            rf"\b{re.escape(month_ascii)}\w*\s*[.,/-]?\s*((?:19|20)\d{{2}})\b",
            normalized,
        )
        if match:
            return date(int(match.group(1)), month_num, 1)

    match = re.search(r"\b((?:19|20)\d{2})\b", normalized)
    if match:
        return date(int(match.group(1)), 1, 1)

    return None


def _parse_point(fragment: str, *, is_end: bool = False) -> Optional[date]:
    fragment = fragment.strip()
    if not fragment:
        return None

    normalized = _ascii_lower(fragment)
    if any(marker in normalized for marker in _PRESENT_MARKERS):
        return date.today().replace(day=1)
    if re.search(r"\bdepuis\b", normalized) and not is_end:
        return _parse_month_year(re.sub(r"\bdepuis\b", "", normalized, count=1))

    return _parse_month_year(fragment)


def _parse_date_range(dates: str) -> Optional[Tuple[date, date]]:
    if not dates or not str(dates).strip():
        return None

    text = str(dates).strip()
    # Do not use \ba\b — it breaks French month names and adds false splits.
    # Do not split on "/" — it is part of MM/YYYY dates (e.g. 04/2022 - present).
    parts = re.split(
        r"\s*(?:-|–|—|\bto\b|\bau\b|\bà\b)\s*",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(parts) == 1:
        normalized_single = _ascii_lower(parts[0])
        if re.search(r"\bdepuis\b", normalized_single):
            start = _parse_point(parts[0], is_end=False)
            if start:
                end = date.today().replace(day=1)
                if end < start:
                    return None
                return start, end
        start = _parse_point(parts[0], is_end=False)
        return (start, start) if start else None

    start = _parse_point(parts[0], is_end=False)
    end = _parse_point(parts[1], is_end=True)
    if not start or not end:
        return None
    if end < start:
        return None
    return start, end


def _parse_duree_months(duree: str) -> Optional[int]:
    if not duree or not str(duree).strip():
        return None

    text = _ascii_lower(str(duree))
    years = 0
    months = 0

    year_match = re.search(r"(\d+)\s*ans?\b", text)
    if year_match:
        years = int(year_match.group(1))

    month_match = re.search(r"(\d+)\s*mois\b", text)
    if month_match:
        months = int(month_match.group(1))

    total = years * 12 + months
    return total if total > 0 else None


def _months_inclusive(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _merge_intervals(intervals: Sequence[Tuple[date, date]]) -> List[Tuple[date, date]]:
    if not intervals:
        return []

    ordered = sorted(intervals, key=lambda item: item[0])
    merged: List[Tuple[date, date]] = [ordered[0]]

    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end or start == _next_month(prev_end):
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def _experience_like_records(data: Dict) -> List[Dict]:
    """Collect date-bearing records from experiences and project periods."""
    records: List[Dict] = []

    experiences = data.get("experiences_professionnelles", [])
    if isinstance(experiences, list):
        records.extend(experiences)

    projets = data.get("projets_realises", [])
    if isinstance(projets, list):
        for proj in projets:
            if not isinstance(proj, dict):
                continue
            periode = str(proj.get("periode", "")).strip()
            if periode:
                records.append({
                    "titre_poste": proj.get("role", ""),
                    "type_contrat": "",
                    "dates": periode,
                    "duree": "",
                })

    return records


def _total_months_from_experiences(experiences: Sequence[Dict]) -> int:
    intervals: List[Tuple[date, date]] = []
    duree_only_months = 0

    for exp in experiences:
        if _is_internship(exp):
            continue

        period = _parse_date_range(str(exp.get("dates", "")))
        if period:
            intervals.append(period)
            continue

        duree_months = _parse_duree_months(str(exp.get("duree", "")))
        if duree_months:
            duree_only_months += duree_months

    if intervals:
        return sum(_months_inclusive(start, end) for start, end in _merge_intervals(intervals))

    return duree_only_months


def _annees_to_months(value: str) -> int:
    if not value:
        return 0
    match = re.search(r"(\d+)", str(value))
    if not match:
        return 0
    return int(match.group(1)) * 12


def _format_annees_experience(total_months: int) -> str:
    years = total_months // 12
    if years < 1:
        return ""
    return f"{years} ans"


def compute_annees_experience(experiences: Sequence[Dict]) -> str:
    """Return formatted years string (e.g. '5 ans') or '' if not computable."""
    if not experiences:
        return ""
    return _format_annees_experience(_total_months_from_experiences(experiences))


def compute_annees_experience_from_cv(data: Dict) -> str:
    """Compute years from experiences + project periods."""
    records = _experience_like_records(data)
    return compute_annees_experience(records)


def enrich_annees_experience(data: Dict) -> Dict:
    """Fill or correct profil_resume.annees_experience from professional timelines."""
    profil = data.setdefault("profil_resume", {})
    current = str(profil.get("annees_experience", "")).strip()

    computed = compute_annees_experience_from_cv(data)
    if not computed:
        return data

    if not current or _annees_to_months(computed) > _annees_to_months(current):
        profil["annees_experience"] = computed

    return data
