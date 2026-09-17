"""Pure helpers for deterministic, fail-closed watcher CV extraction."""
from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Sequence


class ChunkingError(ValueError):
    """Raised when text cannot be chunked within configured safety limits."""


class ExtractionQualityError(ValueError):
    """Raised when a merged extraction is unsafe to persist."""


def _comparison_key(value: Any) -> str:
    """Return an accent-, punctuation-, case-, and whitespace-insensitive key."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _stable_string_key(value: Any) -> str:
    """Case/accent/whitespace key that preserves meaningful punctuation."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def _is_useful(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def chunk_cv_text(
    text: str,
    *,
    chunk_chars: int = 4500,
    overlap_chars: int = 450,
    max_chunks: int = 32,
) -> List[str]:
    """Split CV text deterministically, preferring paragraph and word boundaries."""
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise ValueError("overlap_chars must be >= 0 and smaller than chunk_chars")
    if max_chunks <= 0:
        raise ValueError("max_chunks must be positive")

    source = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not source:
        return []
    if len(source) <= chunk_chars:
        return [source]

    chunks: List[str] = []
    start = 0
    source_length = len(source)

    while start < source_length:
        if len(chunks) >= max_chunks:
            raise ChunkingError(
                f"CV text exceeds configured max_chunks={max_chunks}"
            )

        ideal_end = min(start + chunk_chars, source_length)
        end = ideal_end
        if ideal_end < source_length:
            # Avoid tiny chunks solely because a nearby early paragraph ended.
            minimum_boundary = start + max(1, chunk_chars // 2)
            paragraph_end = source.rfind(
                "\n\n",
                minimum_boundary,
                ideal_end + 1,
            )
            if paragraph_end >= minimum_boundary:
                end = paragraph_end
            else:
                whitespace_end = max(
                    source.rfind(" ", minimum_boundary, ideal_end + 1),
                    source.rfind("\n", minimum_boundary, ideal_end + 1),
                    source.rfind("\t", minimum_boundary, ideal_end + 1),
                )
                if whitespace_end >= minimum_boundary:
                    end = whitespace_end

        if end <= start:
            # Defensive progress guarantee for unusual whitespace/layout input.
            end = ideal_end

        chunk = source[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= source_length:
            break

        desired_start = max(start + 1, end - overlap_chars)
        next_start = desired_start

        # Prefer starting at a nearby paragraph boundary without making overlap
        # dramatically larger or smaller than configured.
        search_radius = min(100, max(10, overlap_chars // 4))
        boundary_start = max(start + 1, desired_start - search_radius)
        boundary_end = min(end, desired_start + search_radius)
        paragraph_start = source.find("\n\n", boundary_start, boundary_end)
        if paragraph_start != -1:
            next_start = paragraph_start + 2
        elif (
            0 < desired_start < source_length
            and source[desired_start - 1].isalnum()
            and source[desired_start].isalnum()
        ):
            # Move to the beginning of the current word when practical.
            word_start = desired_start
            while (
                word_start > start + 1
                and desired_start - word_start < search_radius
                and not source[word_start - 1].isspace()
            ):
                word_start -= 1
            if word_start > start:
                next_start = word_start

        if next_start <= start:
            next_start = end
        start = min(next_start, end)

    return chunks


def _merge_string_lists(target: List[str], incoming: Any) -> None:
    if not isinstance(incoming, list):
        return
    seen = {
        _stable_string_key(value)
        for value in target
        if _stable_string_key(value)
    }
    for value in incoming:
        if not isinstance(value, (str, int, float)):
            continue
        display = str(value).strip()
        key = _stable_string_key(display)
        if display and key and key not in seen:
            target.append(display)
            seen.add(key)


def _fill_missing_scalars(target: Dict[str, Any], incoming: Dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, (dict, list)):
            continue
        if not _is_useful(target.get(key)) and _is_useful(value):
            target[key] = copy.deepcopy(value)


def _record_conflicts(
    left: Dict[str, Any],
    right: Dict[str, Any],
    fields: Iterable[str],
) -> bool:
    for field in fields:
        left_key = _comparison_key(left.get(field))
        right_key = _comparison_key(right.get(field))
        if left_key and right_key and left_key != right_key:
            return True
    return False


def _experience_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    fields = ("titre_poste", "entreprise", "dates")
    if _record_conflicts(left, right, fields):
        return False

    title_left, company_left, dates_left = (
        _comparison_key(left.get(field)) for field in fields
    )
    title_right, company_right, dates_right = (
        _comparison_key(right.get(field)) for field in fields
    )
    return any(
        (
            first_left
            and first_left == first_right
            and second_left
            and second_left == second_right
        )
        for first_left, first_right, second_left, second_right in (
            (company_left, company_right, dates_left, dates_right),
            (title_left, title_right, company_left, company_right),
            (title_left, title_right, dates_left, dates_right),
        )
    )


def _project_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    name_left = _comparison_key(left.get("nom"))
    name_right = _comparison_key(right.get("nom"))
    if not name_left or name_left != name_right:
        return False

    context_left = _comparison_key(left.get("client_ou_contexte"))
    context_right = _comparison_key(right.get("client_ou_contexte"))
    period_left = _comparison_key(left.get("periode"))
    period_right = _comparison_key(right.get("periode"))
    if context_left and context_right and context_left != context_right:
        return False
    if period_left and period_right and period_left != period_right:
        return False
    return bool(
        (context_left and context_left == context_right)
        or (period_left and period_left == period_right)
    )


def _certification_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    name_left = _comparison_key(left.get("nom"))
    name_right = _comparison_key(right.get("nom"))
    if not name_left or name_left != name_right:
        return False
    organization_left = _comparison_key(left.get("organisme"))
    organization_right = _comparison_key(right.get("organisme"))
    date_left = _comparison_key(left.get("date"))
    date_right = _comparison_key(right.get("date"))
    return bool(
        (organization_left and organization_left == organization_right)
        or (date_left and date_left == date_right)
    )


def _formation_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    institution_left = _comparison_key(left.get("institution"))
    institution_right = _comparison_key(right.get("institution"))
    diploma_left = _comparison_key(left.get("diplome"))
    diploma_right = _comparison_key(right.get("diplome"))
    dates_left = _comparison_key(left.get("dates"))
    dates_right = _comparison_key(right.get("dates"))
    return bool(
        (
            institution_left
            and institution_left == institution_right
            and diploma_left
            and diploma_left == diploma_right
        )
        or (
            diploma_left
            and diploma_left == diploma_right
            and dates_left
            and dates_left == dates_right
        )
    )


def _language_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    name_left = _comparison_key(left.get("nom"))
    return bool(name_left and name_left == _comparison_key(right.get("nom")))


def _merge_record(
    target: Dict[str, Any],
    incoming: Dict[str, Any],
    *,
    list_fields: Sequence[str],
) -> None:
    _fill_missing_scalars(target, incoming)
    for field in list_fields:
        existing = target.setdefault(field, [])
        if not isinstance(existing, list):
            existing = []
            target[field] = existing
        _merge_string_lists(existing, incoming.get(field))


def _merge_record_list(
    target: List[Dict[str, Any]],
    incoming: Any,
    *,
    matches: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    list_fields: Sequence[str] = (),
) -> None:
    if not isinstance(incoming, list):
        return
    for record in incoming:
        if not isinstance(record, dict) or not any(
            _is_useful(value) for value in record.values()
        ):
            continue
        matching_records = [
            candidate for candidate in target if matches(candidate, record)
        ]
        if len(matching_records) != 1:
            # Zero matches means a distinct record. Multiple matches means the
            # fragment is ambiguous; retaining it is safer than choosing one.
            target.append(copy.deepcopy(record))
        else:
            _merge_record(
                matching_records[0],
                record,
                list_fields=list_fields,
            )


def merge_chunk_results(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge successful chunk extractions without any additional LLM calls."""
    merged: Dict[str, Any] = {
        "informations_personnelles": {},
        "profil_resume": {
            "description": "",
            "annees_experience": "",
            "specialisations": [],
        },
        "formation": [],
        "certifications": [],
        "competences": {
            "methodologies_et_outils": [],
            "technologies": [],
        },
        "projets_realises": [],
        "langues": [],
        "experiences_professionnelles": [],
        "autres_informations": {
            "interets": [],
            "distinctions": [],
            "publications": [],
            "associations": [],
            "mobilite": "",
            "disponibilite": "",
            "permis": [],
        },
    }

    for result in results:
        if not isinstance(result, dict):
            raise TypeError("Each chunk extraction result must be a JSON object")

        personal = result.get("informations_personnelles")
        if isinstance(personal, dict):
            _fill_missing_scalars(merged["informations_personnelles"], personal)

        profile = result.get("profil_resume")
        if isinstance(profile, dict):
            if not _is_useful(merged["profil_resume"]["description"]):
                description = profile.get("description")
                if _is_useful(description):
                    merged["profil_resume"]["description"] = copy.deepcopy(
                        description
                    )
            _merge_string_lists(
                merged["profil_resume"]["specialisations"],
                profile.get("specialisations"),
            )

        skills = result.get("competences")
        if isinstance(skills, dict):
            for field in ("methodologies_et_outils", "technologies"):
                _merge_string_lists(
                    merged["competences"][field],
                    skills.get(field),
                )

        experiences = result.get(
            "experiences_professionnelles",
            result.get("experiences", []),
        )
        _merge_record_list(
            merged["experiences_professionnelles"],
            experiences,
            matches=_experience_matches,
            list_fields=(
                "missions",
                "realisations",
                "environnement_technique",
                "methodologies",
            ),
        )
        _merge_record_list(
            merged["projets_realises"],
            result.get("projets_realises"),
            matches=_project_matches,
            list_fields=("realisations", "technologies", "methodologies"),
        )
        _merge_record_list(
            merged["formation"],
            result.get("formation"),
            matches=_formation_matches,
        )
        _merge_record_list(
            merged["certifications"],
            result.get("certifications"),
            matches=_certification_matches,
        )
        _merge_record_list(
            merged["langues"],
            result.get("langues"),
            matches=_language_matches,
        )

        other = result.get("autres_informations")
        if isinstance(other, dict):
            _fill_missing_scalars(merged["autres_informations"], other)
            for field in (
                "interets",
                "distinctions",
                "publications",
                "associations",
                "permis",
            ):
                _merge_string_lists(
                    merged["autres_informations"][field],
                    other.get(field),
                )

    # Chunk output is deliberately never authoritative for aggregate years.
    merged["profil_resume"]["annees_experience"] = ""
    return merged


_STRONG_EXPERIENCE_MARKERS = (
    "experience professionnelle",
    "experiences professionnelles",
    "parcours professionnel",
    "professional experience",
    "work experience",
    "employment history",
    "career history",
)
_GENERIC_EXPERIENCE_HEADINGS = frozenset({"experience", "experiences"})


def _has_experience_section(source_text: str) -> bool:
    normalized_source = _comparison_key(source_text)
    if any(
        re.search(rf"\b{re.escape(marker)}\b", normalized_source)
        for marker in _STRONG_EXPERIENCE_MARKERS
    ):
        return True
    return any(
        _comparison_key(line) in _GENERIC_EXPERIENCE_HEADINGS
        for line in source_text.splitlines()
    )


def _has_meaningful_record(records: Any, fields: Sequence[str]) -> bool:
    if not isinstance(records, list):
        return False
    return any(
        isinstance(record, dict)
        and any(_is_useful(record.get(field)) for field in fields)
        for record in records
    )


def validate_extraction_quality(source_text: str, result: Dict[str, Any]) -> None:
    """Apply conservative, deterministic persistence safety checks."""
    personal = result.get("informations_personnelles")
    name = personal.get("nom_complet") if isinstance(personal, dict) else ""
    if not _is_useful(name):
        raise ExtractionQualityError("candidate name is missing")

    experiences = result.get("experiences_professionnelles")
    if not isinstance(experiences, list):
        experiences = []

    has_experiences = _has_meaningful_record(
        experiences,
        (
            "titre_poste",
            "entreprise",
            "dates",
            "missions",
            "realisations",
            "environnement_technique",
        ),
    )
    if _has_experience_section(source_text) and not has_experiences:
        raise ExtractionQualityError(
            "source contains an experience section but no experiences were extracted"
        )

    skills = result.get("competences")
    technologies: List[Any] = []
    tools: List[Any] = []
    if isinstance(skills, dict):
        if isinstance(skills.get("technologies"), list):
            technologies = skills["technologies"]
        if isinstance(skills.get("methodologies_et_outils"), list):
            tools = skills["methodologies_et_outils"]

    has_meaningful_content = any(
        (
            has_experiences,
            _has_meaningful_record(
                result.get("formation"),
                ("institution", "diplome", "dates"),
            ),
            _has_meaningful_record(
                result.get("certifications"),
                ("nom", "organisme", "date"),
            ),
            _has_meaningful_record(
                result.get("projets_realises"),
                ("nom", "client_ou_contexte", "periode", "description"),
            ),
            bool(technologies),
            bool(tools),
        )
    )
    if not has_meaningful_content:
        raise ExtractionQualityError("extraction is structurally empty")
