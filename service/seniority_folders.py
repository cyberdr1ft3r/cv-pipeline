"""Resolve CV_Theque seniority folders that overlap an offer experience range (Action 281)."""
from __future__ import annotations

from typing import Optional

# Fixed seniority bands on CV_Theque (folder names).
SENIORITY_BANDS: dict[str, tuple[Optional[float], Optional[float]]] = {
    "Junior": (0, 2),
    "Confirme": (3, 5),
    "Senior": (6, 10),
    "Expert": (11, None),
}

ALL_SENIORITY_FOLDERS: tuple[str, ...] = tuple(SENIORITY_BANDS.keys())


def ranges_overlap(
    a_min: Optional[float],
    a_max: Optional[float],
    b_min: Optional[float],
    b_max: Optional[float],
) -> bool:
    """Return True when [a_min, a_max] overlaps [b_min, b_max] (null = unbounded)."""
    return (a_min is None or b_max is None or a_min <= b_max) and (
        a_max is None or b_min is None or a_max >= b_min
    )


def resolve_seniority_folders(
    experience_range_min: Optional[float],
    experience_range_max: Optional[float],
) -> list[str]:
    """
    Return seniority folder names whose fixed band overlaps the offer range.
    When both bounds are None, return all seniority levels (legacy fallback).
    """
    if experience_range_min is None and experience_range_max is None:
        return list(ALL_SENIORITY_FOLDERS)

    folders: list[str] = []
    for folder, (band_min, band_max) in SENIORITY_BANDS.items():
        if ranges_overlap(band_min, band_max, experience_range_min, experience_range_max):
            folders.append(folder)
    return folders


# Spec alias (Action 281)
_resolve_seniority_folders = resolve_seniority_folders


def build_matching_experience_context(
    display: Optional[str],
    seniority_label: Optional[str],
) -> str:
    """French LLM hint block for the matching prompt (empty when no range display)."""
    if not display:
        return ""
    label = seniority_label or "non spécifié"
    return (
        f"L'offre requiert {display} d'expérience ({label}).\n"
        "Les candidats correspondant à cette plage doivent obtenir un meilleur score "
        "sur la dimension 'expérience'. Les candidats hors de cette plage (sous-qualifiés "
        "ou surqualifiés) peuvent obtenir un score plus faible sur cette dimension mais "
        "restent considérés si leurs compétences et formation sont solides."
    )
