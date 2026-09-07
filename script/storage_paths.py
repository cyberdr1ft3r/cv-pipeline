"""Single source of truth for the pipeline data workspace (Action 227).

All pipeline storage lives under ``DATA_ROOT`` instead of the historical local
``./data`` folder.  In production ``DATA_ROOT`` is set (via the ``DATA_ROOT``
environment variable) to the mounted SFTP share, e.g.::

    DATA_ROOT=/sftp/cv_tech/files/Data

For local development the variable is left unset and ``DATA_ROOT`` falls back to
``<project_root>/data`` so the local folder keeps working untouched.

Layout (identical regardless of the root):

    DATA_ROOT/current/{folder}/{session_id}   active session outputs
    DATA_ROOT/archive/{session_id}            archived sessions
    DATA_ROOT/api_jobs/{job_id}               job metadata + logs

This module deliberately depends only on the standard library so it can be
imported both from the FastAPI service (``from script.storage_paths import ...``)
and from the pipeline scripts run as files (``import storage_paths``).
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

_logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_DATA_ROOT_ENV = os.getenv("DATA_ROOT", "").strip()
DATA_ROOT = Path(_DATA_ROOT_ENV) if _DATA_ROOT_ENV else (PROJECT_ROOT / "data")

CURRENT_DIR = DATA_ROOT / "current"
ARCHIVE_DIR = DATA_ROOT / "archive"
API_JOBS_DIR = DATA_ROOT / "api_jobs"

# CV bank root (sibling of Data/ under the mounted CV storage folder).
_CV_THEQUE_ENV = os.getenv("CV_LIBRARY_ROOT", "/sftp/cv_tech/files/CV_Theque").strip()
CV_THEQUE_DIR = Path(_CV_THEQUE_ENV) if _CV_THEQUE_ENV else (PROJECT_ROOT / "data" / "CV_Theque")


def current_dir(folder: str) -> Path:
    """Active workspace folder: ``DATA_ROOT/current/{folder}``."""
    return CURRENT_DIR / folder


def session_dir(folder: str, session_id: str) -> Path:
    """Per-session active folder: ``DATA_ROOT/current/{folder}/{session_id}``."""
    return CURRENT_DIR / folder / session_id


def archive_session_dir(session_id: str) -> Path:
    """Per-session archive folder: ``DATA_ROOT/archive/{session_id}``."""
    return ARCHIVE_DIR / session_id


def cv_source_marker_path(session_id: str) -> Path:
    """Marker file recording the CV source directory for a session (Action 230)."""
    return CURRENT_DIR / "logs" / session_id / "cv_source.txt"


def write_cv_source_marker(session_id: str, cv_dir: Path) -> None:
    """Persist the CV source path so archiver/final_result can find CVs without a copy."""
    marker = cv_source_marker_path(session_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(cv_dir), encoding="utf-8")


def archived_cv_source_marker_path(session_id: str) -> Path:
    """Marker file after recruiter archive moves logs to ``archive/{session_id}/logs/``."""
    return ARCHIVE_DIR / session_id / "logs" / "cv_source.txt"


def read_cv_source_marker(session_id: str) -> Optional[Path]:
    """Return the recorded CV source path from current or archive marker."""
    for marker in (cv_source_marker_path(session_id), archived_cv_source_marker_path(session_id)):
        if not marker.exists():
            continue
        text = marker.read_text(encoding="utf-8").strip()
        if text:
            return Path(text)
    return None


def resolve_session_cv_dir(session_id: str) -> Optional[Path]:
    """Resolve where session CV JSONs live (intermediary, CV_Theque marker, or archive).

    Order preserves CV+Offer mode: ``intermediary_structured`` wins when it has JSONs.
    Offer-only sessions fall through to the ``cv_source.txt`` marker (current or archive).
    """
    intermediary = CURRENT_DIR / "intermediary_structured" / session_id
    if intermediary.exists() and any(intermediary.glob("*.json")):
        return intermediary

    marker_dir = read_cv_source_marker(session_id)
    if marker_dir and marker_dir.exists():
        return marker_dir

    archive_extracted = ARCHIVE_DIR / session_id / "cvs" / "extracted"
    if archive_extracted.exists() and any(archive_extracted.glob("*.json")):
        return archive_extracted

    return intermediary if intermediary.exists() else None


# Session-scoped folders under DATA_ROOT/current/
SESSION_DATA_FOLDERS = (
    "offer",
    "intermediary_structured",
    "matching_results",
    "final_result",
    "formatted_cv",
    "logs",
    "tests",
)

# Recruiter archive moves: current/{folder}/{session_id} â†’ archive/{session_id}/{dest}/
ARCHIVE_SESSION_MOVES = (
    ("offer", "offer"),
    ("matching_results", "matching_results"),
    ("final_result", "final_result"),
    ("formatted_cv", "formatted_cv"),
    ("logs", "logs"),
)


def session_current_paths(session_id: str) -> list[Path]:
    """All active session directories under ``current/``."""
    return [CURRENT_DIR / folder / session_id for folder in SESSION_DATA_FOLDERS]


def _best_effort(
    action: Callable[[], None],
    label: str,
    log_info: Optional[Callable[[str], None]] = None,
    log_warn: Optional[Callable[[str], None]] = None,
) -> None:
    try:
        action()
        if log_info:
            log_info(f"[data] {label}")
    except OSError as exc:
        msg = f"[data] Could not {label}: {exc}"
        if log_warn:
            log_warn(msg)
        else:
            _logger.warning(msg)


def _path_exists(path: Path) -> bool:
    """Safe exists check â€” stale sshfs mounts raise OSError instead of False."""
    try:
        return path.exists()
    except OSError:
        return False


def _delete_session_target(
    target: Path,
    log_info: Optional[Callable[[str], None]] = None,
    log_warn: Optional[Callable[[str], None]] = None,
) -> None:
    """Delete one session folder through the mounted filesystem."""
    if _path_exists(target):
        try:
            shutil.rmtree(target)
            if log_info:
                log_info(f"[data] deleted {target} via mount")
        except OSError as exc:
            if log_warn:
                log_warn(f"[data] Mount rmtree failed for {target}: {exc}")
    elif log_info:
        log_info(f"[data] {target} not found on mount")

def cleanup_session_data(
    session_id: str,
    log_info: Optional[Callable[[str], None]] = None,
    log_warn: Optional[Callable[[str], None]] = None,
) -> None:
    """Delete all session data under ``current/`` and ``archive/`` (best-effort)."""
    targets = session_current_paths(session_id) + [ARCHIVE_DIR / session_id]
    for target in targets:
        _delete_session_target(target, log_info=log_info, log_warn=log_warn)


def archive_session_data(
    session_id: str,
    log_info: Optional[Callable[[str], None]] = None,
    log_warn: Optional[Callable[[str], None]] = None,
) -> None:
    """Move recruiter-facing session outputs from ``current/`` to ``archive/``."""
    archive_base = ARCHIVE_DIR / session_id
    for src_folder, dest_folder in ARCHIVE_SESSION_MOVES:
        src = CURRENT_DIR / src_folder / session_id
        if not _path_exists(src):
            continue
        dest = archive_base / dest_folder

        def _move(s=src, d=dest) -> None:
            d.parent.mkdir(parents=True, exist_ok=True)
            if d.exists():
                shutil.rmtree(d)
            shutil.move(str(s), str(d))

        _best_effort(
            _move,
            f"moved {src} â†’ {dest}",
            log_info=log_info,
            log_warn=log_warn,
        )


def safe_relpath(path) -> str:
    """Best-effort display path for logs.

    Returns ``path`` relative to ``PROJECT_ROOT`` when it lives under it (the
    historical behaviour for local ``./data``), otherwise the absolute path.

    Action 229: since data now lives under ``DATA_ROOT`` (e.g. the SFTP mount at
    ``/sftp/cv_tech/files/Data``) which is *outside* ``PROJECT_ROOT`` (``/app``),
    ``Path.relative_to(PROJECT_ROOT)`` would raise ``ValueError`` and crash the
    caller. This helper never raises â€” it is purely for human-readable logging.
    """
    p = Path(path)
    try:
        return str(p.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)

