from __future__ import annotations

import io
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import yaml
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import psycopg2

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config_yaml.yaml"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CONFIG = yaml.safe_load(_f)
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel as PydanticBaseModel

from service.config import (
    API_JOBS_DIR,
    PIPELINE_PG_DSN,
    ENABLE_PG_INGEST,
    CURRENT_DIR,
    ARCHIVE_DIR,
    DATA_ROOT,
    CV_THEQUE_DIR,
    cleanup_session_data,
    archive_session_data,
    safe_relpath,
)
from service.job_store import get_job, init_db, update_job, create_job_unless_active, fail_stale_jobs
from service.models import JobCreateResponse, JobStatusResponse, PipelineArtifacts, PipelineJob
from service.runner import create_job_workspace, start_job_thread, start_phase_thread
from service.cv_storage import (
    StagingWriteError,
    StoragePathError,
    atomic_write_staging_upload,
    normalize_profile,
    resolve_staging_upload_path,
    sanitize_filename_component,
)
from service.google_drive_import import (
    GoogleDriveImportError,
    dedupe_files,
    download_file as download_drive_file,
    get_file_metadata as get_drive_file_metadata,
    list_folder_files as list_drive_folder_files,
)
from service.cv_alignment import (
    align_cv_to_offer,
    create_alignment_workspace,
    list_recent_alignments,
    read_alignment_status,
    resolve_alignment_download,
    write_alignment_status,
)

# Security & Logging Modules


def calculate_job_progress(stage: str, status: str) -> dict[str, int]:
    """Calculate progress percentage for each phase based on job stage and status."""
    progress = {
        "extraction": 0,
        "matching": 0,
        "final": 0,
        "format": 0,
    }

    if status == "failed":
        return progress

    if status == "queued":
        progress["extraction"] = 5
        return progress

    # Map stage to phase progress
    if stage == "preparing_inputs":
        progress["extraction"] = 10
    elif stage == "running_pipeline":
        progress["extraction"] = 30
        progress["matching"] = 30
    elif stage == "running_final":
        progress["extraction"] = 100
        progress["matching"] = 100
        progress["final"] = 50
    elif stage == "running_format":
        progress["extraction"] = 100
        progress["matching"] = 100
        progress["final"] = 100
        progress["format"] = 50
    elif stage == "matching_complete":
        progress["extraction"] = 100
        progress["matching"] = 100
    elif stage == "final_complete":
        progress["extraction"] = 100
        progress["matching"] = 100
        progress["final"] = 100
    elif stage == "format_complete":
        progress["extraction"] = 100
        progress["matching"] = 100
        progress["final"] = 100
        progress["format"] = 100

    return progress
from service.security import (
    verify_token, TokenPayload, create_access_token,
    verify_password, hash_password, SECRET_KEY_VALID,
)
from service.user_store import (
    get_user_by_email, get_user_by_email_any, get_user_by_id, update_last_login, get_sourcers,
    update_full_name, update_password,
    create_user, user_exists, list_users, update_user, soft_delete_user,
    get_user_stats, get_recent_user_creations,
)
from service.audit_store import audit_store
from service.offer_store import (
    create_offer, get_offer_by_id, get_offer_for_recruiter, get_offers_by_recruiter,
    get_offers_by_sourcer, get_sourcer_dashboard_offers, assign_offer, set_offer_job_id, update_offer_job_id,
    update_offer_status, get_dashboard_data, get_active_offer_counts, hard_delete_offer,
    get_assignment_events_for_sourcer,
    get_offer_status_counts, get_recent_offer_events,
    set_offer_status_id, get_offer_statuses,
    sync_offer_skills, fetch_offer_skills, fetch_offer_skills_bulk,
    get_or_create_contract_type, get_or_create_experience_range,
    update_offer_source_metadata,
    fetch_contract_type, fetch_experience_range,
    fetch_contract_types_by_ids, fetch_experience_ranges_by_ids,
    list_contract_types, list_experience_ranges,
    display_experience_range,
)
from service.job_store import (
    get_job_by_session_id, get_job_status_counts, get_recent_job_events,
)
from service.candidate_store import (
    list_candidates as store_list_candidates,
    get_candidate as store_get_candidate,
    get_annees_experience_map as store_get_annees_experience_map,
    update_candidate as store_update_candidate,
    add_note as store_add_note,
    get_notes as store_get_notes,
    get_note as store_get_note,
    update_note as store_update_note,
    delete_note as store_delete_note,
    get_appearances as store_get_appearances,
    get_offer_appearances as store_get_offer_appearances,
    get_appearance_by_id as store_get_appearance_by_id,
    get_candidate_offer_history as store_get_candidate_offer_history,
    get_candidates_matching_offer_skills as store_get_skill_matches,
    get_recruiter_candidate_stats as store_get_recruiter_candidate_stats,
    update_decision as store_update_decision,
    update_appearance_note as store_update_appearance_note,
    backfill_appearances_from_pipeline as store_backfill_appearances,
    sync_appearances_for_offer as store_sync_appearances_for_offer,
    get_matching_statuses as store_get_matching_statuses,
    get_final_statuses as store_get_final_statuses,
    get_format_statuses as store_get_format_statuses,
    update_appearance_status as store_update_appearance_status,
    get_appearance_with_statuses as store_get_appearance_with_statuses,
    get_active_unreliability_flag as store_get_active_unreliability_flag,
    get_active_unreliability_flags_bulk as store_get_active_unreliability_flags_bulk,
    create_unreliability_flag as store_create_unreliability_flag,
    resolve_unreliability_flag as store_resolve_unreliability_flag,
    get_unreliability_flag_by_id as store_get_unreliability_flag_by_id,
    format_unreliability_flag as store_format_unreliability_flag,
)
from service.validation import FileValidator, ValidationError
from service.rate_limit import RateLimiter, ClientIdentifier
from service.logging_config import (
    setup_logging,
    app_logger,
    security_logger,
    request_logger,
    perf_logger,
)


app = FastAPI(title="CV Pipeline API", version="1.0")

# ============================================================================
# STARTUP & INITIALIZATION
# ============================================================================


# â”€â”€ Stale job sweeper (C-7) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Background thread that detects pipeline jobs stuck in "running" and marks them
# failed, so a crashed/hung worker can never leave a job running forever.

_MAX_JOB_DURATION_MINUTES = int(_CONFIG.get("pipeline", {}).get("max_job_duration_minutes", 60))
_STALE_CHECK_INTERVAL_MINUTES = int(_CONFIG.get("pipeline", {}).get("stale_job_check_interval_minutes", 5))


def _sweep_stale_jobs_once() -> None:
    """Single pass: fail any 'running' job whose updated_at is older than the max
    duration. Now backed by a single PostgreSQL UPDATE (C-7 amendment, Action 216)."""
    try:
        failed_ids = fail_stale_jobs(_MAX_JOB_DURATION_MINUTES)
    except Exception as exc:
        app_logger.error(f"[StaleSweeper] Could not sweep stale jobs: {exc}")
        return

    for job_id in failed_ids:
        app_logger.warning(f"[StaleSweeper] Marked stale job as failed: job_id={job_id}")


def _stale_job_sweeper_loop() -> None:
    """Daemon loop â€” runs _sweep_stale_jobs_once every configured interval."""
    interval_seconds = max(1, _STALE_CHECK_INTERVAL_MINUTES) * 60
    while True:
        time.sleep(interval_seconds)
        _sweep_stale_jobs_once()


# â”€â”€ SFTP mount keepalive (Action 262) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Periodic write to DATA_ROOT/.keepalive keeps the sshfs connection active and
# surfaces stale mounts (Errno 107) before the Docker healthcheck fires.

_KEEPALIVE_INTERVAL_SECONDS = 30


def _sftp_keepalive_once() -> None:
    """Write a timestamp under DATA_ROOT to keep the sshfs mount active."""
    try:
        keepalive_path = DATA_ROOT / ".keepalive"
        keepalive_path.write_text(f"{datetime.utcnow().isoformat()}Z\n", encoding="utf-8")
        app_logger.debug("SFTP keepalive OK")
    except OSError as exc:
        if exc.errno == 107:
            app_logger.warning("SFTP mount stale â€” healthcheck will restart")
        else:
            app_logger.debug("SFTP keepalive failed: %s", exc)
    except Exception as exc:
        app_logger.debug("SFTP keepalive failed: %s", exc)


def _sftp_keepalive_loop() -> None:
    """Daemon loop â€” writes DATA_ROOT/.keepalive every 30 seconds."""
    while True:
        time.sleep(_KEEPALIVE_INTERVAL_SECONDS)
        _sftp_keepalive_once()


@app.on_event("startup")
def startup() -> None:
    """Initialize database and logging on startup."""
    # Setup structured logging
    setup_logging()
    
    app_logger.info("API startup - version 1.0.0")
    
    # Guard: SECRET_KEY must be set to a strong value before serving auth routes.
    if not SECRET_KEY_VALID:
        app_logger.error(
            "FATAL: SECRET_KEY is missing, too short (<32 chars), or still the default "
            "placeholder. Set a strong random value in config/.env and restart."
        )
        raise RuntimeError("Invalid SECRET_KEY â€” refusing to start with insecure JWT config.")

    # Initialize database
    try:
        init_db()
        app_logger.info("Database initialized successfully")
    except Exception as e:
        app_logger.error(f"Database initialization failed: {str(e)}")
        # Don't fail startup, database might not be ready yet

    # Start the stale-job sweeper (daemon â€” dies with the process)
    sweeper = threading.Thread(target=_stale_job_sweeper_loop, daemon=True, name="stale-job-sweeper")
    sweeper.start()
    app_logger.info(
        f"Stale-job sweeper started (interval={_STALE_CHECK_INTERVAL_MINUTES}min, "
        f"max_duration={_MAX_JOB_DURATION_MINUTES}min)"
    )

    keepalive = threading.Thread(target=_sftp_keepalive_loop, daemon=True, name="sftp-keepalive")
    keepalive.start()
    app_logger.info(f"SFTP keepalive thread started (interval={_KEEPALIVE_INTERVAL_SECONDS}s)")


# ============================================================================
# MIDDLEWARE & CORS
# ============================================================================

# Request/Response Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests and responses."""
    start_time = time.time()
    
    # Extract request info
    method = request.method
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    
    # Log request
    request_logger.info(f"Request: {method} {path} from {client_ip}")
    
    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log response
        request_logger.info(f"Response: {method} {path} - Status: {response.status_code} - Duration: {duration:.3f}s")
        
        return response
    except Exception as e:
        duration = time.time() - start_time
        request_logger.error(f"Error: {method} {path} - Duration: {duration:.3f}s - Error: {str(e)}")
        security_logger.error(f"Request processing error: {str(e)} at {path}")
        raise


# Enable CORS for frontend communication
# Strip whitespace from each origin â€” env vars with "a, b" (space after comma) would
# otherwise produce [" b"] which the browser's Origin header never matches.
cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:8000,http://0.0.0.0:3000,http://0.0.0.0:3001"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# AUTHENTICATION & SECURITY
# ============================================================================

security = HTTPBearer(auto_error=False)
rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
    requests_per_day=int(os.getenv("RATE_LIMIT_PER_DAY", "10000")),
)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenPayload:
    """Validate JWT from httpOnly cookie (browser) or Authorization header (API clients)."""
    token = request.cookies.get("access_token")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifiÃ©")
    payload = verify_token(token)
    if not payload:
        security_logger.warning("Invalid or expired JWT token presented")
        raise HTTPException(status_code=401, detail="Token invalide ou expirÃ©")
    try:
        user = get_user_by_id(payload.sub)
    except Exception as exc:
        security_logger.error("User state recheck failed for %s: %s", payload.sub, exc)
        raise HTTPException(status_code=503, detail="Authentification temporairement indisponible") from exc
    if not user or not user.is_active:
        security_logger.warning("JWT presented for inactive or missing user: %s", payload.sub)
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")
    if user.deleted_at is not None:
        security_logger.warning("JWT presented for deleted user: %s", payload.sub)
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")
    payload.role = user.role
    payload.email = user.email
    app_logger.info(f"User authenticated: {payload.sub} role={payload.role}")
    return payload


def check_rate_limit(request: Request):
    """Check if client has exceeded rate limit."""
    path = request.url.path
    method = request.method

    # Allow read-only polling endpoints without rate limiting.
    # These are called repeatedly by the UI and should not block user workflows.
    if method == "GET" and (
        path == "/api/v1/health"
        or path == "/api/v1/sessions"
        or path.startswith("/api/v1/jobs/")
        or path.startswith("/api/v1/candidates")
        or (path.startswith("/api/v1/offers/") and path.endswith("/candidates"))
        or (path.startswith("/api/v1/offers/") and path.endswith("/appearances"))
        or (path.startswith("/api/v1/candidates/") and path.endswith("/offer-history"))
    ):
        return

    client_ip = request.client.host if request.client else "unknown"
    client = ClientIdentifier(
        ip=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        api_key=f"{method}:{path}",
    )
    is_allowed = rate_limiter.is_allowed(client)
    
    if not is_allowed:
        remaining = rate_limiter.get_remaining_requests(client)
        security_logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Remaining": str(remaining),
            },
        )


def _check_db() -> dict:
    configured = bool(
        PIPELINE_PG_DSN
        or os.getenv("DATABASE_URL")
        or os.getenv("PGHOST")
    )
    if not configured:
        return {"configured": False}
    dsn = PIPELINE_PG_DSN or os.getenv("DATABASE_URL")
    try:
        if dsn:
            conn = psycopg2.connect(dsn)
        else:
            conn = psycopg2.connect(
                host=os.getenv("PGHOST", "localhost"),
                port=os.getenv("PGPORT", "5432"),
                dbname=os.getenv("PGDATABASE", "postgres"),
                user=os.getenv("PGUSER", "postgres"),
                password=os.getenv("PGPASSWORD", ""),
            )
        conn.close()
        return {"configured": True, "ok": True}
    except Exception as exc:
        return {"configured": True, "ok": False, "error": str(exc)}


# â”€â”€ Input sanitization (S-CRIT-3) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Session ids are timestamps (YYYYMMDDHHMMSS); job ids are canonical UUID4.
_SESSION_ID_RE = re.compile(r"^\d{14}$")
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
# Permissive UUID (any version) â€” used for auth.users path params.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _validate_session_id(value: Optional[str]) -> Optional[str]:
    """S-CRIT-3 A: a session id must be exactly 14 digits or absent. Prevents path
    traversal when the value is joined into data/ subdirectories."""
    if value is None or value == "":
        return None
    if not _SESSION_ID_RE.match(value):
        raise HTTPException(status_code=400, detail="Format de session invalide")
    return value


def _validate_job_id(job_id: str) -> None:
    """S-CRIT-3 B: reject anything that is not a canonical UUID4. Returns 404 without
    revealing the expected format."""
    if not _UUID4_RE.match(job_id or ""):
        raise HTTPException(status_code=404, detail="job not found")


def _safe_upload_filename(filename: Optional[str]) -> str:
    """S-CRIT-3 C/D: strip any directory component and reject unsafe names so an
    uploaded filename can never escape its target directory."""
    try:
        safe = sanitize_filename_component(filename)
    except StoragePathError:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    return safe


def _write_upload(upload: UploadFile, target_dir: Path) -> Path:
    """Write uploaded file to disk with validation."""
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_upload_filename(upload.filename)  # S-CRIT-3 C
    upload_suffix = Path(safe_name).suffix
    
    # Validate file before saving
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=upload_suffix) as tmp:
            content = upload.file.read()
            tmp.write(content)
            tmp.flush()
            
            # Validate file using content type from upload
            try:
                FileValidator.validate_file(tmp.name)
            except ValidationError as err:
                security_logger.warning(f"Invalid file rejected: {upload.filename} - {str(err)}")
                raise
            
            app_logger.info(f"File validated: {upload.filename}")
    finally:
        try:
            os.unlink(tmp.name)
        except:
            pass
    
    file_path = target_dir / safe_name
    with file_path.open("wb") as f:
        f.write(content)
    
    return file_path


def _job_access_denied() -> None:
    raise HTTPException(status_code=404, detail="job not found")


def _current_user_can_access_job(job: PipelineJob, current_user: TokenPayload) -> bool:
    if current_user.role == "admin":
        return True
    if job.created_by and str(job.created_by) == current_user.sub:
        return True
    if job.offer_id:
        offer = get_offer_by_id(job.offer_id)
        if not offer:
            return False
        if current_user.role == "recruiter" and str(offer.created_by) == current_user.sub:
            return True
        if current_user.role == "sourcer" and str(offer.assigned_to) == current_user.sub:
            return True
    return False


def _get_accessible_job(job_id: str, current_user: TokenPayload) -> PipelineJob:
    _validate_job_id(job_id)
    job = get_job(job_id)
    if not job or not _current_user_can_access_job(job, current_user):
        _job_access_denied()
    return job


def _assert_session_access(session_id: str, current_user: TokenPayload) -> PipelineJob:
    job = get_job_by_session_id(session_id)
    if not job or not _current_user_can_access_job(job, current_user):
        raise HTTPException(status_code=404, detail="Session introuvable")
    return job


def _persist_tests_upload(job: PipelineJob, tests_path: Path) -> Path:
    """Store test scores under job inputs and archive a copy under session tests/."""
    session_tests_dir = CURRENT_DIR / "tests" / job.session_id
    session_tests_dir.mkdir(parents=True, exist_ok=True)
    archived = session_tests_dir / tests_path.name
    if not archived.exists() or archived.stat().st_mtime < tests_path.stat().st_mtime:
        shutil.copy2(tests_path, archived)
    job.artifacts.tests_file_path = str(tests_path)
    update_job(job)
    app_logger.info(
        f"Test scores saved for job {job.job_id}: "
        f"{safe_relpath(tests_path)} (archived: {safe_relpath(archived)})"
    )
    return archived


def _parse_tests_upload(form) -> UploadFile | None:
    """Extract tests_file from multipart form (tolerant of empty filename edge cases).

    ``await request.form()`` yields ``starlette.datastructures.UploadFile`` parts,
    which are not ``isinstance(..., fastapi.UploadFile)`` â€” duck-type instead.
    """
    candidate = form.get("tests_file")
    if candidate is None:
        return None
    if not (hasattr(candidate, "filename") and hasattr(candidate, "read")):
        return None
    if candidate.filename and candidate.filename.strip():
        return candidate
    # Some clients omit filename; accept if the part looks like a readable upload.
    if hasattr(candidate, "seek"):
        return candidate
    return None


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================


def _check_sftp_mount(path: Path) -> bool:
    """Return True when the sshfs mount responds to a directory listing."""
    try:
        os.listdir(path)
        return True
    except OSError:
        return False
    except Exception:
        return False


@app.get("/api/v1/health")
async def health(request: Request) -> dict:
    """Health check endpoint for monitoring."""
    check_rate_limit(request)  # Even health check respects rate limits
    
    db_status = _check_db()
    data_path = str(DATA_ROOT)
    cv_theque_path = str(CV_THEQUE_DIR)
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat(),
        "db": db_status,
        "pg_ingest_enabled": ENABLE_PG_INGEST,
        "api_version": "1.0.0",
        "sftp_data": {
            "mounted": _check_sftp_mount(DATA_ROOT),
            "path": data_path,
        },
        "sftp_cv_theque": {
            "mounted": _check_sftp_mount(CV_THEQUE_DIR),
            "path": cv_theque_path,
        },
    }


# ============================================================================
# JOB MANAGEMENT ENDPOINTS
# ============================================================================


@app.post("/api/v1/jobs", response_model=JobCreateResponse, status_code=202)
def create_job(
    request: Request,
    job_offer: Optional[UploadFile] = File(None),
    cv_files: list[UploadFile] | None = File(None),
    archive: bool = Form(True),
    reuse_session_id: str | None = Form(None),
    offer_only: bool = Form(False),
    # â”€â”€ Offer-from-SFTP fields (sourcer launching an assigned offer) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    offer_sftp_path: Optional[str] = Form(None),   # absolute SFTP path to offer file
    preset_session_id: Optional[str] = Form(None), # session_id pre-set at offer creation
    linked_offer_id: Optional[str] = Form(None),   # offers.job_offers.id to link
    limit_count: Optional[int] = Form(None),      # max CVs to score during matching
    current_user: TokenPayload = Depends(get_current_user),
) -> JobCreateResponse:
    """Create a new CV processing job.

    Supports three modes:
    - Standard: upload CV files + offer file
    - Reuse: reuse existing session CVs + upload offer file
    - Offer-only (from assigned offer): provide offer_sftp_path + preset_session_id
    """
    start_time = time.time()
    check_rate_limit(request)

    # S-CRIT-3 A: reject malformed session ids before they reach the filesystem.
    reuse_session_id = _validate_session_id(reuse_session_id)
    preset_session_id = _validate_session_id(preset_session_id)
    if reuse_session_id:
        _assert_session_access(reuse_session_id, current_user)

    # Fix 2 (Action 220): when launching from an assigned offer, the session_id and
    # offer file path are taken authoritatively from the DB â€” never generate a new
    # session_id and never trust a mismatched client-supplied preset.
    _linked_offer = None
    if linked_offer_id:
        _linked_offer = get_offer_by_id(linked_offer_id)
        if not _linked_offer:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        source_path = _resolve_offer_source_file(_linked_offer)
        offer_sftp_path = str(source_path)

    if limit_count is not None and limit_count < 1:
        raise HTTPException(status_code=400, detail="limit_count must be a positive integer")

    # â”€â”€ Offer-from-SFTP mode (sourcer launches from assigned offer) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    is_sftp_offer_mode = bool(linked_offer_id or (offer_sftp_path and preset_session_id))

    if is_sftp_offer_mode:
        # Download offer file from SFTP to local job workspace
        if cv_files or reuse_session_id:
            raise HTTPException(status_code=400, detail="offer_sftp_path ne peut pas Ãªtre combinÃ© avec des CVs ou reuse_session_id")
        offer_only = True  # Treat as offer_only for runner logic

    # Validate input mode
    if offer_only and not is_sftp_offer_mode:
        if cv_files:
            raise HTTPException(status_code=400, detail="CV files not allowed in offer_only mode")
        if reuse_session_id:
            raise HTTPException(status_code=400, detail="reuse_session_id not allowed in offer_only mode")
        if not job_offer:
            raise HTTPException(status_code=400, detail="job_offer file is required for offer_only mode")
    elif not offer_only and not is_sftp_offer_mode:
        if not job_offer:
            raise HTTPException(status_code=400, detail="job_offer file is required")
        if not cv_files and not reuse_session_id:
            raise HTTPException(status_code=400, detail="Either cv_files or reuse_session_id must be provided")
        if cv_files and reuse_session_id:
            raise HTTPException(status_code=400, detail="Cannot provide both cv_files and reuse_session_id")

    try:
        is_offer_only_mode = offer_only
        is_reuse_mode = reuse_session_id is not None

        if is_sftp_offer_mode:
            mode_str = "offer_sftp"
            cv_count_str = 0
        elif is_offer_only_mode:
            mode_str = "offer_only"
            cv_count_str = 0
        elif is_reuse_mode:
            mode_str = "reuse"
            cv_count_str = 0
        else:
            mode_str = "standard"
            cv_count_str = len(cv_files) if cv_files else 0

        # offer_name set below â€” may be overridden in SFTP mode after discovery
        offer_name = (job_offer.filename if job_offer else None) or offer_sftp_path or "sftp-offer"

        # session_id: linked-offer retries always get a fresh processing session.
        if is_sftp_offer_mode:
            session_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") if linked_offer_id else preset_session_id
        elif not is_offer_only_mode:
            session_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        else:
            session_id = None  # Will be set after SFTP CV loading

        job_id = str(uuid4())
        paths = create_job_workspace(job_id)

        # Resolve offer file: either upload from form or discover+download from SFTP
        if is_sftp_offer_mode:
            # Action 227: the offer lives on the shared data root (mounted SFTP
            # share in prod, ./data locally). Use session_id as the single source
            # of truth: list {DATA_ROOT}/current/offer/{session_id}/ and take the
            # first file found â€” no network session required.
            offer_src_dir = CURRENT_DIR / "offer" / session_id
            try:
                dir_files = (
                    [p.name for p in offer_src_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
                    if offer_src_dir.exists()
                    else []
                )
            except OSError:
                dir_files = []

            if not dir_files:
                # Fallback: use offer_sftp_path directly if directory listing fails
                if offer_sftp_path:
                    _hint = Path(offer_sftp_path)
                    dir_files = [_hint.name]
                    offer_src_dir = _hint.parent
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Aucun fichier d'offre trouvÃ© pour la session {session_id}"
                    )

            offer_filename_sftp = dir_files[0]  # Only one file per offer session
            src_full_path = offer_src_dir / offer_filename_sftp
            # Action 230: preserve the original filename in the job workspace so
            # downstream steps never re-write a generic offer.txt alongside it.
            local_offer = paths["offer_dir"] / offer_filename_sftp

            try:
                shutil.copy2(src_full_path, local_offer)
            except OSError as exc:
                raise HTTPException(status_code=503, detail=f"Impossible de lire le fichier d'offre : {exc}")
            offer_name = offer_filename_sftp  # Use discovered filename
            offer_path = local_offer
        else:
            offer_path = _write_upload(job_offer, paths["offer_dir"])

        app_logger.info(f"Job creation started: {offer_name}, CVs: {cv_count_str}, mode: {mode_str}")
        
        # Handle based on mode
        if is_offer_only_mode:
            # Offer only mode: CVs will be loaded from SFTP
            cv_count = 0
            input_mode = "offer_only"
            input_cv_dir = None  # Will be set after SFTP loading
        elif is_reuse_mode:
            # Reuse mode: no CV uploads, just offer
            cv_count = 0
            input_mode = "offer_only_reuse"
            input_cv_dir = str(CURRENT_DIR / "intermediary_structured" / reuse_session_id)
        else:
            # Standard mode: process uploaded CVs
            cv_count = 0
            for cv in cv_files:
                _write_upload(cv, paths["cvs_dir"])
                cv_count += 1
            input_mode = "cv_folder_offer"
            input_cv_dir = str(paths["cvs_dir"])

        archive_enabled = True
        artifacts = PipelineArtifacts(
            input_offer_path=str(offer_path),
            input_cv_dir=input_cv_dir,
            matching_results_dir=str(CURRENT_DIR / "matching_results" / session_id) if session_id else None,
            final_results_dir=str(CURRENT_DIR / "final_result" / session_id) if session_id else None,
            formatted_cv_dir=str(CURRENT_DIR / "formatted_cv" / session_id) if session_id else None,
            archive_dir=str(ARCHIVE_DIR / session_id) if session_id else None,
            transformed_json_path=None,
            reuse_session_id=reuse_session_id,
            detected_profile=None,  # Will be set during pipeline execution
            detected_seniority=None,  # Will be set during pipeline execution
            sftp_retry_count=0,
        )

        job = PipelineJob(
            job_id=job_id,
            session_id=session_id or "pending",  # Use "pending" for offer_only mode until CVs are loaded
            status="queued",
            stage="preparing_inputs",
            created_at=datetime.utcnow(),
            input_mode=input_mode,
            offer_filename=offer_name,  # job_offer is None in SFTP mode; offer_name is always set
            cv_count=cv_count,
            archive_enabled=archive_enabled,
            format_cvs=False,
            template_name=None,
            limit_count=limit_count,
            offer_id=linked_offer_id,  # FK to offers.job_offers(id); None for /pipeline launches
            created_by=current_user.sub,  # S-CRIT-2: authenticated user UUID
            artifacts=artifacts,
        )

        created_job, job = create_job_unless_active(job)
        job_id = job.job_id
        if not created_job:
            return JobCreateResponse(job_id=job.job_id, session_id=job.session_id or "pending", status=job.status)
        start_job_thread(job_id)

        # Link job back to the offer record (if launched from an assigned offer)
        _offer_title = None
        if linked_offer_id:
            # Fix 3 (Action 223): atomically link job_id AND set status_id = 3 (in_progress).
            try:
                update_offer_job_id(linked_offer_id, job_id, 3)
            except Exception as exc:
                app_logger.warning(f"Could not link job {job_id} to offer {linked_offer_id}: {exc}")
            try:
                _linked = get_offer_by_id(linked_offer_id)
                _offer_title = _linked.title if _linked else None
            except Exception:
                _offer_title = None

            audit_store.log_event(
                event_type="pipeline_launched",
                description=f"Pipeline lancÃ© pour l'offre {_offer_title or session_id or job_id}",
                actor_id=current_user.sub,
                target_id=linked_offer_id,
                target_type="offer",
                metadata={"job_id": job_id, "session_id": session_id},
            )
        else:
            audit_store.log_event(
                event_type="pipeline_launched",
                description=f"Pipeline lancÃ© ({session_id or job_id})",
                actor_id=current_user.sub,
                target_id=job_id,
                target_type="job",
                metadata={"session_id": session_id},
            )

        duration = time.time() - start_time
        perf_logger.info(f"Job creation operation took {duration * 1000:.0f}ms, processed {cv_count} items")
        app_logger.info(f"Job created successfully: {job_id}, session: {session_id or 'pending'}, CVs: {cv_count}, mode: {input_mode}, duration: {duration:.2f}s")

        return JobCreateResponse(job_id=job_id, session_id=session_id or "pending", status=job.status)
    except ValidationError as e:
        security_logger.warning(f"File validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        app_logger.exception("Job creation failed")
        raise HTTPException(
            status_code=500,
            detail="Une erreur interne est survenue lors de la crÃ©ation du job.",
        ) from e


@app.get("/api/v1/sessions")
async def list_sessions(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """List available CV extraction sessions for reuse."""
    check_rate_limit(request)
    
    try:
        intermediary_dir = CURRENT_DIR / "intermediary_structured"
        
        sessions = []
        
        if intermediary_dir.exists():
            for session_path in sorted(intermediary_dir.iterdir(), reverse=True):
                if session_path.is_dir():
                    # Count CVs in this session
                    cv_count = len(list(session_path.glob("*.json")))
                    
                    # Try to get creation date from session_id
                    # Session IDs are formatted as YYYYMMDDHHmmss
                    session_id = session_path.name
                    try:
                        created_date = datetime.strptime(session_id, "%Y%m%d%H%M%S").isoformat()
                    except ValueError:
                        created_date = datetime.utcnow().isoformat()
                    
                    if cv_count > 0:
                        if current_user.role != "admin":
                            session_job = get_job_by_session_id(session_id)
                            if not session_job or not _current_user_can_access_job(session_job, current_user):
                                continue
                        sessions.append({
                            "session_id": session_id,
                            "created_date": created_date,
                            "cv_count": cv_count,
                        })
        
        app_logger.info(f"Sessions listed: {len(sessions)} sessions")
        return {
            "sessions": sessions,
            "total": len(sessions),
        }
    except Exception as e:
        app_logger.error(f"Failed to list sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> JobStatusResponse:
    """Get status of a deployment job."""
    check_rate_limit(request)
    _validate_job_id(job_id)

    job = _get_accessible_job(job_id, current_user)

    progress = calculate_job_progress(job.stage, job.status)
    return JobStatusResponse(job=job, artifacts=job.artifacts.dict(), progress=progress)


@app.get("/api/v1/jobs/{job_id}/logs")
async def get_job_logs(
    request: Request,
    job_id: str,
    tail: int | None = None,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get logs for a deployment job."""
    check_rate_limit(request)
    _get_accessible_job(job_id, current_user)

    job_dir = API_JOBS_DIR / job_id
    logs_dir = job_dir / "logs"
    stdout_path = logs_dir / "pipeline_stdout.log"
    stderr_path = logs_dir / "pipeline_stderr.log"
    if not stdout_path.exists() and not stderr_path.exists():
        raise HTTPException(status_code=404, detail="logs not found")

    content = ""
    if stdout_path.exists():
        content += stdout_path.read_text(encoding="utf-8", errors="ignore")
    if stderr_path.exists():
        content += "\n\n=== STDERR ===\n"
        content += stderr_path.read_text(encoding="utf-8", errors="ignore")

    if tail:
        lines = content.splitlines()
        content = "\n".join(lines[-tail:])

    return PlainTextResponse(content)


@app.get("/api/v1/jobs/{job_id}/progress")
async def get_job_progress(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get real-time progress based on log analysis."""
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)

    job_dir = API_JOBS_DIR / job_id
    stdout_path = job_dir / "logs" / "pipeline_stdout.log"

    extraction_progress = 1
    matching_progress = 0
    final_progress = 0
    format_progress = 0

    extraction_detail = "Initialisation..."
    matching_detail = ""
    final_detail = ""
    format_detail = ""

    if stdout_path.exists():
        content = stdout_path.read_text(encoding="utf-8", errors="ignore")

        if job.stage in ["matching_complete", "final_complete", "format_complete"]:
            extraction_progress = 100
            matching_progress = 100
            extraction_detail = "Termine"
            matching_detail = "Termine"

        if job.stage in ["final_complete", "format_complete"]:
            final_progress = 100
            final_detail = "Termine"

        if job.stage == "format_complete":
            format_progress = 100
            format_detail = "Termine"

        if job.stage in ["running_pipeline", "queued", "preparing_inputs"]:
            extraction_markers = [
                ("CV EXTRACTION PIPELINE", 5, "Preparation..."),
                ("Found", 10, "Analyse des fichiers..."),
                ("Extracting text", 25, "Extraction du texte..."),
                ("Calling OpenRouter API", 40, "Appel API en cours..."),
                ("Validating data", 60, "Validation des donnees..."),
                ("Spelling correction", 75, "Correction orthographique..."),
                ("JSON saved", 90, "Sauvegarde..."),
                ("PIPELINE SUMMARY", 100, "Termine"),
            ]

            for marker, prog, detail in extraction_markers:
                if marker in content:
                    extraction_progress = max(extraction_progress, prog)
                    extraction_detail = detail

            if "SUCCESS" in content and "PIPELINE SUMMARY" not in content:
                extraction_progress = max(extraction_progress, 95)
                extraction_detail = "Traitement en cours..."

            matching_markers = [
                ("Found", 5, "Chargement des CVs..."),
                ("Scoring", 30, "Scoring des candidats..."),
                ("overall_score", 70, "Analyse terminee..."),
                ("Results saved", 100, "Termine"),
            ]

            for marker, prog, detail in matching_markers:
                if marker in content:
                    matching_progress = max(matching_progress, prog)
                    matching_detail = detail

            final_markers = [
                ("FINAL RESULT AGGREGATION", 5, "Initialisation..."),
                ("Loading matching results", 20, "Chargement des resultats..."),
                ("Loading job offer description", 35, "Chargement de l'offre..."),
                ("Parsing test scores", 45, "Analyse des tests..."),
                ("Extracting emails", 55, "Extraction des emails..."),
                ("Matching candidates", 65, "Matching des candidats..."),
                ("Generating final rankings", 80, "Generation des classements..."),
                ("Results saved to", 100, "Termine"),
            ]

            for marker, prog, detail in final_markers:
                if marker in content:
                    final_progress = max(final_progress, prog)
                    final_detail = detail

            format_markers = [
                ("Traitement session", 5, "Preparation..."),
                ("Recherche des CVs intermediaires", 15, "Recherche des CVs..."),
                ("Recherche des resultats finaux", 25, "Chargement des resultats..."),
                ("candidat", 40, "Preparation des candidats..."),
                ("Job title extracted", 55, "Extraction du titre..."),
                ("HTML genere", 75, "Generation HTML..."),
                ("PDF genere", 100, "Termine"),
            ]

            for marker, prog, detail in format_markers:
                if marker in content:
                    format_progress = max(format_progress, prog)
                    format_detail = detail

    return {
        "extraction": extraction_progress,
        "matching": matching_progress,
        "final": final_progress,
        "format": format_progress,
        "details": {
            "extraction": extraction_detail,
            "matching": matching_detail,
            "final": final_detail,
            "format": format_detail,
        }
    }


@app.get("/api/v1/jobs/{job_id}/results")
async def get_job_results(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get results of a completed job."""
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)
    return JSONResponse(
        {
            "job_id": job.job_id,
            "session_id": job.session_id,
            "status": job.status,
            "artifacts": job.artifacts.dict(),
            "exit_codes": {
                "pipeline": job.pipeline_exit_code,
                "transformer": job.transform_exit_code,
                "ingest": job.ingest_exit_code,
            },
            "error": job.error_message,
        }
    )


_SFTP_UNAVAILABLE = "Stockage SFTP temporairement inaccessible"
_SFTP_WRITE_UNAVAILABLE = (
    "Impossible d'enregistrer la fiche de poste. RÃ©essayez dans quelques instants."
)


def _path_exists_safe(path: Path) -> bool:
    """Safe exists â€” stale sshfs mounts raise OSError instead of False."""
    try:
        return path.exists()
    except OSError:
        return False


def _safe_dir_has_files(path: Path) -> bool:
    """Return True when a directory exists and contains at least one entry."""
    try:
        return path.exists() and any(path.iterdir())
    except OSError:
        return False


def _write_data_share_bytes(dest_path: Path, content: bytes) -> Path:
    """Write bytes under the mounted DATA_ROOT filesystem."""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content)
        if dest_path.stat().st_size != len(content):
            raise OSError(f"write size mismatch for {dest_path}")
        return dest_path
    except OSError as exc:
        app_logger.error("Data share write failed path=%s err=%s", dest_path, exc)
        raise HTTPException(status_code=503, detail="Stockage local indisponible") from exc


def _read_json_file(local_path: Path) -> dict:
    try:
        return json.loads(local_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fichier JSON introuvable") from exc
    except OSError as exc:
        app_logger.warning("JSON read failed path=%s err=%s", local_path, exc)
        raise HTTPException(status_code=503, detail="Stockage local indisponible") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Fichier JSON invalide") from exc


def _read_matching_candidate_count(session_id: str) -> Optional[int]:
    """Return the number of successfully scored candidates from matching_results JSON."""
    if not session_id:
        return None
    try:
        match_path = _resolve_matching_result_path(session_id)
        if not match_path:
            return None
        payload = _read_json_file(match_path)
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            return len(candidates)
        total = payload.get("total_candidates")
        if isinstance(total, int):
            return total
    except Exception as exc:
        app_logger.debug("matching count read failed session=%s: %s", session_id, exc)
    return None

def _resolve_matching_result_path(session_id: str) -> Optional[Path]:
    """Locate the first matching-results JSON under current/ or archive/."""
    candidate_dirs = [
        CURRENT_DIR / "matching_results" / session_id,
        ARCHIVE_DIR / session_id / "matching",
        ARCHIVE_DIR / session_id / "matching_results",
    ]
    for directory in candidate_dirs:
        if not _path_exists_safe(directory):
            continue
        found = sorted(directory.glob("*.json"))
        if found:
            return found[0]
    return None


_formatted_candidates_cache: dict[str, tuple[float, list[str]]] = {}
_FORMATTED_CANDIDATES_CACHE_TTL = 30.0


def _list_formatted_candidate_names(session_id: str) -> list[str]:
    """Return unique filename stems for formatted PDF/HTML outputs."""
    now = time.time()
    cached = _formatted_candidates_cache.get(session_id)
    if cached and now - cached[0] < _FORMATTED_CANDIDATES_CACHE_TTL:
        return cached[1]
    names: set[str] = set()
    source_dir = _resolve_formatted_cv_dir(session_id)
    if source_dir:
        for file_path in source_dir.glob("*"):
            if file_path.is_file() and file_path.suffix in (".pdf", ".html"):
                names.add(file_path.stem)
    result = sorted(names)
    _formatted_candidates_cache[session_id] = (now, result)
    return result


def _file_response_local(local_path: Path, filename: str | None = None) -> FileResponse:
    """Return a FileResponse from the mounted filesystem."""
    try:
        local_path.read_bytes()
        return FileResponse(local_path, filename=filename or local_path.name)
    except OSError as exc:
        app_logger.warning("artifact read failed path=%s err=%s", local_path, exc)
        raise HTTPException(status_code=503, detail="Stockage local indisponible") from exc


@app.get("/api/v1/jobs/{job_id}/matching")
async def get_matching_results(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get matching results for a job."""
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)
    session_id = job.session_id
    match_path = _resolve_matching_result_path(session_id)
    if not match_path:
        raise HTTPException(status_code=404, detail="no matching result files found")
    payload = _read_json_file(match_path)
    raw_candidates = payload.get("candidates") or []
    candidate_ids = [
        str(item.get("candidate_id"))
        for item in raw_candidates
        if item.get("candidate_id")
    ]
    annees_by_id = store_get_annees_experience_map(candidate_ids)
    results = []
    for idx, item in enumerate(raw_candidates, 1):
        cid = str(item.get("candidate_id") or "")
        db_years = annees_by_id.get(cid) if cid else None
        results.append(
            {
                "rank": idx,
                "candidateName": item.get("candidate_name"),
                "candidateId": item.get("candidate_id"),
                "matchScore": item.get("overall_score"),
                "experience": db_years or item.get("annees_experience") or "N/A",
                "skills": item.get("skills") or [],
                "summary": item.get("recommendation"),
                "skillsMatch": item.get("skills_match"),
                "experienceMatch": item.get("experience_match"),
                "educationMatch": item.get("education_match"),
            }
        )
    return {
        "jobId": job_id,
        "sessionId": session_id,
        "totalCandidates": len(results),
        "results": results,
    }


def _resolve_final_result_path(session_id: str) -> Optional[Path]:
    """Locate final_result.json under current/ or archive/ (Action 238)."""
    for candidate in (
        CURRENT_DIR / "final_result" / session_id / "final_result.json",
        ARCHIVE_DIR / session_id / "final_result" / "final_result.json",
        ARCHIVE_DIR / session_id / "final" / "final_result.json",  # legacy path
    ):
        if _path_exists_safe(candidate):
            return candidate
    return None


def _parse_final_result_rows(payload: dict) -> list[dict]:
    """Normalize final_result.json candidates (list or dict) to API rows."""
    raw = payload.get("candidates")
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = [
            {"name": name, **data} if isinstance(data, dict) else {"name": name}
            for name, data in raw.items()
        ]
    else:
        items = []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "candidate_name": item.get("name") or item.get("candidate_name"),
                "overall_score": item.get("overall_score"),
                "test_score": item.get("test_score"),
                "final_score": item.get("final_score"),
                "rank": item.get("rank"),
            }
        )
    return rows


@app.get("/api/v1/jobs/{job_id}/final")
async def get_final_table(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get final scoring table for a job."""
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)
    session_id = job.session_id
    final_path = _resolve_final_result_path(session_id)
    if not final_path:
        raise HTTPException(status_code=404, detail="final_result.json not found")
    payload = _read_json_file(final_path)
    return {"session_id": session_id, "rows": _parse_final_result_rows(payload)}


@app.post("/api/v1/jobs/{job_id}/final", status_code=202)
async def run_final_phase(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Run final phase of CV processing pipeline.

    The optional test file is parsed defensively from the request rather than via a
    ``File(None)`` parameter: declaring the file param makes Starlette parse the body
    during dependency resolution, and an empty multipart body (sent by the frontend
    when no file is selected) raises "There was an error parsing the body" (400)
    before any handler code runs. Parsing the form ourselves lets us treat a missing
    or malformed body as "no file" and proceed normally.
    """
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)

    tests_file: UploadFile | None = None
    candidates_raw: str | None = None
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        try:
            form = await request.form()
            tests_file = _parse_tests_upload(form)
            raw_selection = form.get("candidates")
            if isinstance(raw_selection, str) and raw_selection.strip():
                candidates_raw = raw_selection
        except Exception as exc:
            app_logger.warning(f"Final phase form parse failed for {job_id}: {exc}")
            tests_file = None

    selected: list[str] | None = None
    if candidates_raw:
        try:
            parsed = json.loads(candidates_raw)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="SÃ©lection de candidats invalide.")
        if not isinstance(parsed, list):
            raise HTTPException(status_code=400, detail="SÃ©lection de candidats invalide.")
        selected = [str(name) for name in parsed if str(name).strip()]
        if not selected:
            raise HTTPException(status_code=400, detail="SÃ©lectionnez au moins un candidat.")

    try:
        job_dir = API_JOBS_DIR / job_id
        selection_path = job_dir / "final_selection.json"
        if selected:
            selection_path.parent.mkdir(parents=True, exist_ok=True)
            selection_path.write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
        elif selection_path.exists():
            selection_path.unlink()

        if tests_file:
            tests_path = _write_upload(tests_file, job_dir / "inputs")
            _persist_tests_upload(job, tests_path)
        else:
            app_logger.info(f"Final phase for {job_id}: no test scores file in request")
        start_phase_thread(job_id, phase="final")
        app_logger.info(f"Final phase started: {job_id}")
        return {"job_id": job_id, "status": "running", "has_tests_file": bool(tests_file)}
    except ValidationError as e:
        security_logger.warning(f"Final phase validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        app_logger.error(f"Final phase start failed: {str(e)} for job {job_id}")
        raise HTTPException(status_code=500, detail="Final phase start failed")


@app.post("/api/v1/jobs/{job_id}/format", status_code=202)
async def run_format_phase(
    request: Request,
    job_id: str,
    template: str | None = Form(None),
    limit: int | None = Form(None),
    candidates: str | None = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Run formatting phase of CV processing pipeline.

    The recruiter chooses either a count (``limit`` â€” top N final candidates) or an
    explicit manual selection (``candidates`` â€” a JSON array of candidate names, max 10).
    A manual selection takes precedence and is persisted to a per-job selection file
    that the runner passes to the CV generator; the ``limit`` is cleared in that case.
    """
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)

    # Parse an optional manual candidate selection.
    selected: list[str] | None = None
    if candidates:
        try:
            parsed = json.loads(candidates)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="SÃ©lection de candidats invalide.")
        if not isinstance(parsed, list):
            raise HTTPException(status_code=400, detail="SÃ©lection de candidats invalide.")
        selected = [str(name) for name in parsed if str(name).strip()][:10]
        if not selected:
            selected = None

    try:
        job.format_cvs = True
        job.template_name = template
        # Manual selection overrides the count.
        job.limit_count = None if selected else limit

        # Persist / clear the manual selection file the runner reads.
        selection_path = API_JOBS_DIR / job_id / "format_selection.json"
        if selected:
            selection_path.parent.mkdir(parents=True, exist_ok=True)
            selection_path.write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
        elif selection_path.exists():
            selection_path.unlink()

        update_job(job)
        start_phase_thread(job_id, phase="format")
        app_logger.info(
            f"Format phase started: {job_id} template={template} "
            f"limit={job.limit_count} manual={len(selected) if selected else 0}"
        )
        return {"job_id": job_id, "status": "running"}
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Format phase start failed: {str(e)} for job {job_id}")
        raise HTTPException(status_code=500, detail="Format phase start failed")


@app.get("/api/v1/jobs/{job_id}/formatted-candidates")
async def list_formatted_candidates(
    request: Request,
    job_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List candidate names whose CV was actually formatted (from formatted_cv/ output)."""
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)
    session_id = job.session_id
    if not session_id:
        return {"candidates": []}
    return {"candidates": _list_formatted_candidate_names(session_id)}


@app.get("/api/v1/jobs/{job_id}/download/{artifact}")
async def download_artifact(
    request: Request,
    job_id: str,
    artifact: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Download processing artifacts."""
    check_rate_limit(request)
    job = _get_accessible_job(job_id, current_user)

    session_id = job.session_id

    if artifact == "final_result":
        file_path = _resolve_final_result_path(session_id)
        if not file_path:
            raise HTTPException(status_code=404, detail="final_result.json not found")
        app_logger.info(f"Artifact downloaded: {artifact} for job {job_id}")
        return _file_response_local(file_path)

    if artifact == "matching_result":
        match_path = _resolve_matching_result_path(session_id)
        if not match_path:
            raise HTTPException(status_code=404, detail="no matching result files found")
        app_logger.info(f"Artifact downloaded: {artifact} for job {job_id}")
        return _file_response_local(match_path)

    if artifact == "archive_zip":
        archive_dir = ARCHIVE_DIR / session_id
        if not archive_dir.exists():
            raise HTTPException(status_code=404, detail="archive directory not found")
        zip_path = API_JOBS_DIR / job_id / f"archive_{session_id}.zip"
        if not zip_path.exists():
            shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(archive_dir))
        app_logger.info(f"Artifact downloaded: {artifact} for job {job_id}")
        return FileResponse(zip_path)

    if artifact == "formatted_zip":
        _empty_fmt_msg = (
            "Aucun CV formatÃ© disponible â€” le formatage a peut-Ãªtre Ã©chouÃ©. Relancez le formatage."
        )
        zip_filename = f"Formatted_CVs_{session_id}.zip"
        zip_path = API_JOBS_DIR / job_id / zip_filename
        source_dir = _resolve_formatted_cv_dir(session_id)
        remote_dir = None

        if source_dir and not zip_path.exists():
            try:
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for file_path in source_dir.glob("*"):
                        if file_path.is_file() and file_path.suffix in (".pdf", ".html"):
                            zf.write(file_path, arcname=file_path.name)
            except OSError as exc:
                app_logger.warning(
                    "formatted zip mount build failed session=%s err=%s â€” using local filesystem only",
                    session_id,
                    exc,
                )
                source_dir = None

        if not source_dir and not zip_path.exists():
            raise HTTPException(status_code=404, detail=_empty_fmt_msg)

        if not zip_path.exists():
            raise HTTPException(status_code=404, detail=_empty_fmt_msg)

        app_logger.info(f"Artifact downloaded: {artifact} for job {job_id}")
        return FileResponse(zip_path, filename=zip_filename)

    if artifact == "transformed_session":
        if not job.artifacts.transformed_json_path:
            raise HTTPException(status_code=404, detail="transformed session not available")
        file_path = Path(job.artifacts.transformed_json_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="artifact file not found")
        app_logger.info(f"Artifact downloaded: {artifact} for job {job_id}")
        return FileResponse(file_path)

    raise HTTPException(status_code=404, detail="unknown artifact")


# â”€â”€ AUTH â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class _LoginRequest(PydanticBaseModel):
    email: str
    password: str


@app.post("/api/v1/auth/login")
async def auth_login(body: _LoginRequest, response: Response):
    """Authenticate with email + password. Sets httpOnly access_token cookie."""
    user = get_user_by_email_any(body.email)
    # Account-state checks happen BEFORE password verification (per spec).
    # No-enumeration: a missing user and a wrong password share the same message.
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Ce compte a Ã©tÃ© supprimÃ©. Contactez votre administrateur.")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Ce compte a Ã©tÃ© dÃ©sactivÃ©. Contactez votre administrateur.")
    from service.security import verify_password as _verify
    if not _verify(body.password, user.hashed_password):
        security_logger.warning(f"Failed login attempt for {body.email}")
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})
    update_last_login(str(user.id))
    audit_store.log_event(
        event_type="user_login",
        description=f"{user.full_name} s'est connectÃ©",
        actor_id=str(user.id),
        actor_name=user.full_name,
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,   # set True in production behind HTTPS
        max_age=1800,   # 30 minutes
        path="/",       # explicit â€” ensures cookie is sent for all API paths
    )
    security_logger.info(f"Successful login: {user.email} role={user.role}")
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


@app.post("/api/v1/auth/logout")
async def auth_logout(response: Response):
    """Clear the access_token cookie."""
    response.delete_cookie(key="access_token", httponly=True, samesite="lax", path="/")
    return {"message": "DÃ©connexion rÃ©ussie"}


@app.get("/api/v1/auth/me")
async def auth_me(current_user: TokenPayload = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    user = get_user_by_id(current_user.sub)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


class _UpdateProfileRequest(PydanticBaseModel):
    full_name: str


class _UpdatePasswordRequest(PydanticBaseModel):
    current_password: str
    new_password: str
    confirm_password: str


@app.patch("/api/v1/auth/profile")
async def auth_update_profile(
    body: _UpdateProfileRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update the authenticated user's display name."""
    name = body.full_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Le nom complet ne peut pas Ãªtre vide.")
    update_full_name(current_user.sub, name)
    user = get_user_by_id(current_user.sub)
    return {"full_name": user.full_name, "email": user.email, "role": user.role}


@app.patch("/api/v1/auth/password")
async def auth_update_password(
    body: _UpdatePasswordRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Change the authenticated user's password."""
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractÃ¨res.")
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas.")
    user = get_user_by_id(current_user.sub)
    if not user or not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect.")
    update_password(current_user.sub, hash_password(body.new_password))
    return {"message": "Mot de passe mis Ã  jour avec succÃ¨s"}


# â”€â”€ Role helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _require_role(*roles: str):
    """FastAPI dependency factory â€” raises 403 if current user's role is not in allowed roles."""
    async def _check(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="AccÃ¨s refusÃ©")
        return current_user
    return _check


# â”€â”€ Offer file constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Action 227: offer files are written directly onto the shared data root
# ({DATA_ROOT}/current/offer/{session_id}) via the mount â€” see create_offer_endpoint.
_OFFER_VALID_EXTENSIONS = {
    ".txt", ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png",
    ".xlsx", ".xls", ".xlsm",
}
_OFFER_SOURCE_MISSING_DETAIL = "Le fichier source de cette offre est introuvable. Veuillez rÃ©importer l'offre."


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_offer_source_relpath(offer_id: str, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".bin"
    return f"offers/{offer_id}/original{ext}"


def _resolve_data_root_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return DATA_ROOT / path


def _atomic_write_offer_source(offer_id: str, filename: str, content: bytes) -> tuple[Path, str, int, str]:
    relpath = _stable_offer_source_relpath(offer_id, filename)
    dest = DATA_ROOT / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_name(f".{dest.name}.{uuid4().hex}.tmp")
    with tmp_path.open("wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    actual_size = tmp_path.stat().st_size
    expected_size = len(content)
    if actual_size != expected_size:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Ã‰criture incomplÃ¨te du fichier source de l'offre.")
    checksum = _sha256_file(tmp_path)
    if checksum != _sha256_bytes(content):
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="VÃ©rification du fichier source de l'offre impossible.")
    os.replace(tmp_path, dest)
    return dest, relpath, expected_size, checksum


def _copy_legacy_offer_to_stable(offer, legacy_path: Path) -> Path:
    if not legacy_path.exists() or not legacy_path.is_file():
        raise HTTPException(status_code=409, detail=_OFFER_SOURCE_MISSING_DETAIL)
    expected_size = offer.source_file_size
    expected_sha = offer.source_sha256
    actual_size = legacy_path.stat().st_size
    actual_sha = _sha256_file(legacy_path)
    if expected_size is not None and int(expected_size) != actual_size:
        raise HTTPException(status_code=409, detail=_OFFER_SOURCE_MISSING_DETAIL)
    if expected_sha and expected_sha != actual_sha:
        raise HTTPException(status_code=409, detail=_OFFER_SOURCE_MISSING_DETAIL)

    filename = offer.source_original_filename or legacy_path.name
    relpath = _stable_offer_source_relpath(str(offer.id), filename)
    dest = DATA_ROOT / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_name(f".{dest.name}.{uuid4().hex}.tmp")
    shutil.copy2(legacy_path, tmp_path)
    if tmp_path.stat().st_size != actual_size or _sha256_file(tmp_path) != actual_sha:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Migration du fichier source de l'offre impossible.")
    os.replace(tmp_path, dest)
    update_offer_source_metadata(
        str(offer.id),
        relpath,
        filename,
        actual_size,
        actual_sha,
        offer_sftp_path=str(dest),
    )
    return dest


def _resolve_offer_source_file(offer) -> Path:
    stable_path = _resolve_data_root_path(getattr(offer, "source_storage_path", None))
    if stable_path and stable_path.exists() and stable_path.is_file():
        if offer.source_file_size is not None and stable_path.stat().st_size != int(offer.source_file_size):
            raise HTTPException(status_code=409, detail=_OFFER_SOURCE_MISSING_DETAIL)
        if offer.source_sha256 and _sha256_file(stable_path) != offer.source_sha256:
            raise HTTPException(status_code=409, detail=_OFFER_SOURCE_MISSING_DETAIL)
        return stable_path

    legacy_candidates = [
        _resolve_data_root_path(getattr(offer, "offer_sftp_path", None)),
        _resolve_data_root_path(getattr(offer, "file_path", None)),
    ]
    for legacy_path in legacy_candidates:
        if legacy_path and legacy_path.exists() and legacy_path.is_file():
            return _copy_legacy_offer_to_stable(offer, legacy_path)

    raise HTTPException(status_code=409, detail=_OFFER_SOURCE_MISSING_DETAIL)


# â”€â”€ OFFER MANAGEMENT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@app.post("/api/v1/offers/preview-metadata")
async def preview_offer_metadata(
    file: UploadFile = File(...),
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Extract offer metadata from a file without creating an offer (for form pre-fill)."""
    from service.offer_parser import get_offer_parser as _get_parser

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Un fichier de fiche de poste est requis.")
    safe_filename = _safe_upload_filename(file.filename)
    ext = Path(safe_filename).suffix.lower()
    if ext not in _OFFER_VALID_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supportÃ© : {ext}")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 50 Mo).")

    extracted_text = ""
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        parser = _get_parser()
        extracted_text = parser.extract_text_from_file(tmp_path)
    except Exception as exc:
        app_logger.warning(f"Preview metadata text extraction failed: {exc}")
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    metadata: dict = {}
    if extracted_text.strip():
        try:
            metadata = _get_parser().extract_offer_metadata(extracted_text)
        except Exception as exc:
            app_logger.warning(f"Preview metadata LLM extraction failed: {exc}")

    contract_code = metadata.get("contract_type") or "CDI"
    contract_type_id = get_or_create_contract_type(contract_code)
    contract_type = fetch_contract_type(contract_type_id)

    min_y = metadata.get("experience_min_years")
    max_y = metadata.get("experience_max_years")
    experience_range = None
    experience_range_id = None
    if min_y is not None or max_y is not None:
        experience_range_id = get_or_create_experience_range(min_y, max_y)
        experience_range = fetch_experience_range(experience_range_id)

    return {
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "skills": metadata.get("skills") or [],
        "experience_level": metadata.get("experience_level"),
        "location": metadata.get("location"),
        "salary_range": metadata.get("salary_range"),
        "contract_type": contract_type,
        "contract_type_code": contract_code,
        "experience_range": experience_range,
        "experience_range_id": experience_range_id,
    }


@app.post("/api/v1/offers", status_code=201)
async def create_offer_endpoint(
    request: Request,
    file: UploadFile = File(...),                   # required â€” offer document
    sourcer_id: Optional[str] = Form(None),         # optional â€” assign immediately
    contract_type_id: Optional[int] = Form(None),
    contract_type: Optional[str] = Form(None),
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Upload an offer file; LLM extracts metadata. Optionally assigns to a sourcer."""
    from datetime import datetime as _dt
    from service.offer_parser import get_offer_parser as _get_parser

    # â”€â”€ Validate file â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Un fichier de fiche de poste est requis.")
    # Fix 3 (Action 220): keep the original (sanitized) filename instead of "offer.{ext}".
    safe_filename = _safe_upload_filename(file.filename)
    ext = Path(safe_filename).suffix.lower()
    if ext not in _OFFER_VALID_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supportÃ© : {ext}. AcceptÃ©s : {', '.join(sorted(_OFFER_VALID_EXTENSIONS))}",
        )
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 50 Mo).")

    # â”€â”€ Validate sourcer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if sourcer_id:
        sourcer = get_user_by_id(sourcer_id)
        if not sourcer or sourcer.role not in ("sourcer", "admin"):
            raise HTTPException(status_code=400, detail="Utilisateur sourcer introuvable.")

    # â”€â”€ Write the offer onto the shared data root â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Action 227: the data root is a mounted SFTP share in production
    # ({DATA_ROOT}/current/offer/{session_id}) and ./data/current/offer locally.
    # We write directly through the mount instead of opening a network session.
    offer_id = str(uuid4())
    dest_path, source_relpath, source_size, source_sha = _atomic_write_offer_source(
        offer_id,
        safe_filename,
        content,
    )
    session_id = None
    sftp_path: Optional[str] = str(dest_path)  # absolute path on the shared data root
    extracted_text = ""

    extract_path = dest_path

    # â”€â”€ Extract raw text from file â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        parser = _get_parser()
        extracted_text = parser.extract_text_from_file(extract_path)
    except Exception as exc:
        app_logger.warning(f"Text extraction failed for offer {file.filename}: {exc}")
    finally:
        if extract_path != dest_path:
            try:
                extract_path.unlink()
            except OSError:
                pass

    # â”€â”€ LLM metadata extraction (non-blocking â€” offer created even if it fails) â”€â”€
    metadata: dict = {}
    if extracted_text.strip():
        try:
            parser = _get_parser()
            metadata = parser.extract_offer_metadata(extracted_text)
        except Exception as exc:
            app_logger.warning(f"Offer metadata extraction failed: {exc}")

    if contract_type_id:
        resolved_contract_type_id = int(contract_type_id)
    elif contract_type and contract_type.strip():
        resolved_contract_type_id = get_or_create_contract_type(contract_type.strip())
    else:
        resolved_contract_type_id = get_or_create_contract_type(
            metadata.get("contract_type") or "CDI"
        )

    min_y = metadata.get("experience_min_years")
    max_y = metadata.get("experience_max_years")
    experience_range_id = None
    if min_y is not None or max_y is not None:
        experience_range_id = get_or_create_experience_range(min_y, max_y)

    # â”€â”€ Persist offer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    skill_names = metadata.get("skills") or []
    offer = create_offer(
        offer_id=offer_id,
        title=metadata.get("title") or Path(file.filename).stem,
        description=metadata.get("description") or "",
        created_by=current_user.sub,
        experience_level=metadata.get("experience_level"),
        location=metadata.get("location"),
        salary_range=metadata.get("salary_range"),
        session_id=session_id,
        offer_sftp_path=sftp_path,
        source_storage_path=source_relpath,
        source_original_filename=safe_filename,
        source_file_size=source_size,
        source_sha256=source_sha,
        contract_type_id=resolved_contract_type_id,
        experience_range_id=experience_range_id,
    )

    try:
        sync_offer_skills(str(offer.id), skill_names)
    except Exception as exc:
        app_logger.warning("sync_offer_skills failed for offer %s: %s", offer.id, exc)

    audit_store.log_event(
        event_type="offer_created",
        description=f"Offre crÃ©Ã©e: {offer.title}",
        actor_id=current_user.sub,
        target_id=str(offer.id),
        target_type="offer",
    )

    # â”€â”€ Assign to sourcer if requested â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if sourcer_id:
        updated = assign_offer(str(offer.id), sourcer_id, current_user.sub)
        if updated:
            offer = updated
            _sourcer = get_user_by_id(sourcer_id)
            audit_store.log_event(
                event_type="offer_assigned",
                description=f"Offre '{offer.title}' assignÃ©e Ã  {_sourcer.full_name if _sourcer else 'un sourceur'}",
                actor_id=current_user.sub,
                target_id=str(offer.id),
                target_type="offer",
            )

    skills = fetch_offer_skills(str(offer.id))
    ct = fetch_contract_type(offer.contract_type_id or 1)
    er = fetch_experience_range(offer.experience_range_id) if offer.experience_range_id else None
    return _offer_to_dict(offer, skills=skills, contract_type=ct, experience_range=er)


@app.get("/api/v1/ref/contract-types")
async def ref_contract_types(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Active contract types for offer forms."""
    return {"contract_types": list_contract_types(active_only=True)}


@app.get("/api/v1/ref/experience-ranges")
async def ref_experience_ranges(
    current_user: TokenPayload = Depends(get_current_user),
):
    """All experience ranges ordered by min/max years."""
    return {"experience_ranges": list_experience_ranges()}


@app.get("/api/v1/ref/matching-statuses")
async def ref_matching_statuses(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Matching phase statuses for candidate pipeline."""
    try:
        return {"matching_statuses": store_get_matching_statuses()}
    except Exception as exc:
        app_logger.warning("get_matching_statuses failed: %s", exc)
        raise HTTPException(status_code=503, detail="RÃ©fÃ©rentiel indisponible") from exc


@app.get("/api/v1/ref/final-statuses")
async def ref_final_statuses(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Final result phase statuses for candidate pipeline."""
    try:
        return {"final_statuses": store_get_final_statuses()}
    except Exception as exc:
        app_logger.warning("get_final_statuses failed: %s", exc)
        raise HTTPException(status_code=503, detail="RÃ©fÃ©rentiel indisponible") from exc


@app.get("/api/v1/ref/format-statuses")
async def ref_format_statuses(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Format/client phase statuses for candidate pipeline."""
    try:
        return {"format_statuses": store_get_format_statuses()}
    except Exception as exc:
        app_logger.warning("get_format_statuses failed: %s", exc)
        raise HTTPException(status_code=503, detail="RÃ©fÃ©rentiel indisponible") from exc


@app.get("/api/v1/offers")
async def list_offers(
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Return all offers created by the current recruiter, with job status if applicable."""
    offers = get_offers_by_recruiter(current_user.sub)
    skills_map = fetch_offer_skills_bulk([str(o.id) for o in offers])
    ct_map = fetch_contract_types_by_ids([o.contract_type_id or 1 for o in offers])
    er_map = fetch_experience_ranges_by_ids(
        [o.experience_range_id for o in offers if o.experience_range_id]
    )
    return {
        "offers": [
            _offer_with_job(
                o,
                skills=skills_map.get(str(o.id), []),
                contract_type=ct_map.get(o.contract_type_id or 1),
                experience_range=er_map.get(o.experience_range_id) if o.experience_range_id else None,
            )
            for o in offers
        ]
    }


@app.patch("/api/v1/offers/{offer_id}/assign")
async def assign_offer_endpoint(
    offer_id: str,
    body: dict,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Assign a job offer to a sourcer."""
    sourcer_id = body.get("sourcer_id")
    if not sourcer_id:
        raise HTTPException(status_code=400, detail="sourcer_id est requis")

    offer = get_offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if str(offer.created_by) != current_user.sub and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="AccÃ¨s refusÃ©")

    # Business rule: an offer can only be (re)assigned before the sourcer launches
    # the pipeline. Once status_id >= 3 (En cours) the assignment is locked, because
    # work, artifacts and a linked job already exist for the current sourcer.
    is_reassignment = offer.assigned_to is not None
    if is_reassignment and (getattr(offer, "status_id", 0) or 0) >= 3:
        raise HTTPException(
            status_code=409,
            detail="Le pipeline a dÃ©jÃ  Ã©tÃ© lancÃ© : la rÃ©assignation de cette offre n'est plus possible.",
        )

    # Verify sourcer exists
    from service.user_store import get_user_by_id as _get_user
    sourcer = _get_user(sourcer_id)
    if not sourcer or sourcer.role not in ("sourcer", "admin"):
        raise HTTPException(status_code=400, detail="Utilisateur sourcer introuvable")

    updated = assign_offer(offer_id, sourcer_id, current_user.sub)
    if not updated:
        raise HTTPException(status_code=404, detail="Offre introuvable ou supprimÃ©e")
    audit_store.log_event(
        event_type="offer_reassigned" if is_reassignment else "offer_assigned",
        description=(
            f"Offre '{updated.title}' rÃ©assignÃ©e Ã  {sourcer.full_name}"
            if is_reassignment
            else f"Offre '{updated.title}' assignÃ©e Ã  {sourcer.full_name}"
        ),
        actor_id=current_user.sub,
        target_id=str(updated.id),
        target_type="offer",
    )
    return _offer_to_dict(updated)


@app.get("/api/v1/users/sourcers")
async def list_sourcers(
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Return all active sourcer users with their current active offer count."""
    sourcers = get_sourcers()
    counts = get_active_offer_counts()
    return {
        "sourcers": [
            {
                "id": str(s.id),
                "full_name": s.full_name,
                "email": s.email,
                "active_offers_count": counts.get(str(s.id), 0),
            }
            for s in sourcers
        ]
    }


@app.get("/api/v1/my-offers")
async def my_offers(
    current_user: TokenPayload = Depends(_require_role("sourcer", "admin")),
):
    """Return all offers assigned to the current sourcer, with job status."""
    offers = get_offers_by_sourcer(current_user.sub)
    ct_map = fetch_contract_types_by_ids([o.contract_type_id or 1 for o in offers])
    er_map = fetch_experience_ranges_by_ids(
        [o.experience_range_id for o in offers if o.experience_range_id]
    )
    return {
        "offers": [
            _offer_with_job(
                o,
                contract_type=ct_map.get(o.contract_type_id or 1),
                experience_range=er_map.get(o.experience_range_id) if o.experience_range_id else None,
            )
            for o in offers
        ]
    }


@app.get("/api/v1/my-offers/{offer_id}")
async def my_offer_detail(
    offer_id: str,
    current_user: TokenPayload = Depends(_require_role("sourcer", "admin")),
):
    """Return full detail of a single offer assigned to the current sourcer."""
    offer = get_offer_by_id(offer_id)
    if not offer or (str(offer.assigned_to) != current_user.sub and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="Offre introuvable")
    ct = fetch_contract_type(offer.contract_type_id or 1)
    er = fetch_experience_range(offer.experience_range_id) if offer.experience_range_id else None
    d = _offer_with_job(offer, contract_type=ct, experience_range=er)
    recruiter = get_user_by_id(str(offer.created_by)) if offer.created_by else None
    d["recruiter_name"] = recruiter.full_name if recruiter else None
    if offer.session_id:
        job = get_job_by_session_id(offer.session_id)
        if job and d.get("job"):
            d["job"]["cv_count"] = job.cv_count
            d["job"]["created_at"] = job.created_at.isoformat() if job.created_at else None
    return d


@app.get("/api/v1/sourcer/dashboard")
async def sourcer_dashboard(
    current_user: TokenPayload = Depends(_require_role("sourcer", "admin")),
):
    """Return KPIs for the sourcer dashboard.

    Fix 2 (Action 223): all KPIs derive from the authoritative ``status_id`` and the
    offerâ†’job link (``offer.job_id``), not the legacy text status. Terminal success
    is the job status ``succeeded`` (``completed`` accepted as a legacy alias).
    """
    # KPI scope: all assigned offers (incl. final_result/formatted), not status_id <= 4.
    offers = get_sourcer_dashboard_offers(current_user.sub)

    pipelines_launched = 0
    total_cvs = 0
    by_status = {"pending": 0, "running": 0, "completed": 0, "failed": 0}

    for o in offers:
        job = get_job(o.job_id) if o.job_id else None
        if job is None and o.session_id:
            job = get_job_by_session_id(o.session_id)
        if job:
            pipelines_launched += 1
            if job.status in ("succeeded", "completed"):
                scored = (
                    _read_matching_candidate_count(job.session_id)
                    if job.session_id
                    else None
                )
                total_cvs += scored if scored is not None else (job.cv_count or 0)

        if job and job.status == "failed":
            by_status["failed"] += 1
        elif o.status_id >= 4:           # matched, final_result, formatted â€” sourcing done
            by_status["completed"] += 1
        elif o.status_id == 3:           # in_progress
            by_status["running"] += 1
        else:                            # assigned (2) with no pipeline yet
            by_status["pending"] += 1

    # Recent activity now sourced from the audit log (Improvement 2E),
    # scoped to this sourcer's own pipeline actions.
    _audit_rows = audit_store.get_recent_activity(
        limit=5,
        actor_id=current_user.sub,
        event_type=["pipeline_launched", "pipeline_completed", "pipeline_failed"],
    )
    recent_activity = [
        {
            "type": r["event_type"],
            "description": r["description"],
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in _audit_rows
    ]

    return {
        "assigned_offers_count": len(offers),
        "pipelines_launched": pipelines_launched,
        "total_cvs_matched": total_cvs,
        "offers_by_status": by_status,
        "recent_activity": recent_activity,
    }


@app.get("/api/v1/offers/statuses")
async def list_offer_statuses(
    current_user: TokenPayload = Depends(_require_role("sourcer", "recruiter", "admin")),
):
    """Return offer statuses for building UI tabs/filters, scoped by role.

    Sourcers only ever see status_id <= 4 and 'all'-visible statuses; recruiters
    and admins see the full lifecycle.

    NOTE: This static route MUST be declared before the parameterized
    ``/api/v1/offers/{offer_id}`` route, otherwise FastAPI matches "statuses"
    as an offer_id and raises a UUID parse error.
    """
    statuses = get_offer_statuses()
    if current_user.role == "sourcer":
        statuses = [s for s in statuses if s["id"] <= 4 and s["visible_to"] == "all"]
    return {"statuses": statuses}


@app.get("/api/v1/offers/{offer_id}")
async def get_offer_detail(
    offer_id: str,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Return full detail of a single offer (must belong to current recruiter)."""
    offer = get_offer_for_recruiter(offer_id, current_user.sub)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    skills = fetch_offer_skills(offer_id)
    ct = fetch_contract_type(offer.contract_type_id or 1)
    er = fetch_experience_range(offer.experience_range_id) if offer.experience_range_id else None
    d = _offer_with_job(offer, skills=skills, contract_type=ct, experience_range=er)

    # Enrich with sourcer info if assigned
    assigned_sourcer = None
    if offer.assigned_to:
        sourcer = get_user_by_id(str(offer.assigned_to))
        if sourcer:
            assigned_sourcer = {"full_name": sourcer.full_name, "email": sourcer.email}

    # Enrich job with cv_count
    if d.get("job") and offer.session_id:
        job = get_job_by_session_id(offer.session_id)
        if job:
            d["job"]["cv_count"] = job.cv_count
            d["job"]["created_at"] = job.created_at.isoformat() if job.created_at else None

    d["assigned_sourcer"] = assigned_sourcer
    return d


@app.get("/api/v1/offers/{offer_id}/skill-matches")
async def get_offer_skill_matches(
    offer_id: str,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Return top candidates ranked by skill overlap with the offer's required skills."""
    offer = get_offer_for_recruiter(offer_id, current_user.sub)
    if not offer and current_user.role == "admin":
        offer = get_offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    try:
        matches = store_get_skill_matches(offer_id, limit=20)
    except Exception as exc:
        app_logger.warning("get_candidates_matching_offer_skills failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    return {"offer_id": offer_id, "matches": matches}


class _UpdateStatusRequest(PydanticBaseModel):
    status: str


@app.patch("/api/v1/offers/{offer_id}/status")
async def update_offer_status_endpoint(
    offer_id: str,
    body: _UpdateStatusRequest,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Manual status transition by recruiter (e.g. archive). Accepts a status code."""
    # Recruiter-settable codes (automatic lifecycle states are driven by the pipeline).
    allowed = {"open", "archived"}
    code = "archived" if body.status == "closed" else body.status  # legacy alias
    if code not in allowed:
        raise HTTPException(status_code=400, detail=f"Statut invalide. Valeurs acceptÃ©es : {', '.join(sorted(allowed))}")

    offer = get_offer_for_recruiter(offer_id, current_user.sub)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    # Action 232: move session files to archive/ before marking status_id = 7.
    if code == "archived" and offer.session_id:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            archive_session_data,
            offer.session_id,
            app_logger.info,
            app_logger.warning,
        )

    updated = update_offer_status(offer_id, code, current_user.sub)
    if not updated:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    if code == "archived":
        audit_store.log_event(
            event_type="offer_archived",
            description=f"Offre '{updated.title}' archivÃ©e",
            actor_id=current_user.sub,
            target_id=str(updated.id),
            target_type="offer",
            metadata={"status_id": 7},
        )
    else:
        audit_store.log_event(
            event_type="offer_reopened",
            description=f"Offre Â« {updated.title} Â» â†’ {updated.status_label}",
            actor_id=current_user.sub,
            target_id=str(updated.id),
            target_type="offer",
            metadata={"status_code": updated.status_code},
        )
    return _offer_to_dict(updated)


@app.delete("/api/v1/offers/{offer_id}", status_code=204)
async def delete_offer_endpoint(
    offer_id: str,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Hard-delete an offer, linked jobs, and all session data on the data root."""
    offer = get_offer_for_recruiter(offer_id, current_user.sub)
    if not offer and current_user.role == "admin":
        offer = get_offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    session_id = offer.session_id
    title = offer.title
    offer_uuid = str(offer.id)

    # Audit before DB deletion so the offer_deleted row survives cleanup.
    audit_store.log_event(
        event_type="offer_deleted",
        description=f"Offre '{title}' supprimÃ©e dÃ©finitivement",
        actor_id=current_user.sub,
        target_id=offer_uuid,
        target_type="offer",
    )

    # SFTP / data-root cleanup â€” best-effort, never blocks DB deletion.
    if session_id:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            cleanup_session_data,
            session_id,
            app_logger.info,
            app_logger.warning,
        )

    hard_delete_offer(offer_id)


@app.get("/api/v1/recruiter/dashboard")
async def recruiter_dashboard(
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Return aggregated KPIs for the recruiter dashboard."""
    data = get_dashboard_data(current_user.sub)
    by_stage = data["offers_by_stage"]
    total_offers = sum(by_stage.values())

    offers = get_offers_by_recruiter(current_user.sub)
    pipelines_launched = 0
    pipelines_completed = 0
    pipelines_running = 0
    pipelines_failed = 0
    total_cvs_scored = 0
    sourcer_completed: dict[str, dict] = {}

    for o in offers:
        job = get_job(o.job_id) if o.job_id else None
        if job is None and o.session_id:
            job = get_job_by_session_id(o.session_id)
        if not job:
            continue
        pipelines_launched += 1
        if job.status in ("succeeded", "completed"):
            pipelines_completed += 1
            scored = (
                _read_matching_candidate_count(job.session_id)
                if job.session_id
                else None
            )
            total_cvs_scored += scored if scored is not None else (job.cv_count or 0)
            if o.assigned_to:
                sid = str(o.assigned_to)
                if sid not in sourcer_completed:
                    sourcer = get_user_by_id(sid)
                    sourcer_completed[sid] = {
                        "full_name": sourcer.full_name if sourcer else "Sourceur",
                        "completed_pipelines": 0,
                    }
                sourcer_completed[sid]["completed_pipelines"] += 1
        elif job.status == "running":
            pipelines_running += 1
        elif job.status == "failed":
            pipelines_failed += 1

    top_sourcer = None
    if sourcer_completed:
        top_sourcer = max(
            sourcer_completed.values(),
            key=lambda s: s["completed_pipelines"],
        )
    elif data.get("top_sourcer"):
        top_sourcer = {
            "full_name": data["top_sourcer"]["full_name"],
            "completed_pipelines": 0,
            "assignment_count": data["top_sourcer"].get("assignment_count", 0),
        }

    try:
        candidate_stats = store_get_recruiter_candidate_stats(current_user.sub)
    except Exception as exc:
        app_logger.warning("recruiter candidate stats failed: %s", exc)
        candidate_stats = {
            "candidates_seen": 0,
            "candidates_shortlisted": 0,
            "candidates_in_process": 0,
            "candidates_hired": 0,
            "average_matching_score": None,
        }

    _audit_rows = audit_store.get_recent_activity(
        limit=8,
        actor_id=current_user.sub,
        event_type=[
            "offer_created", "offer_assigned", "offer_archived",
            "offer_deleted", "pipeline_completed", "pipeline_failed",
        ],
    )
    activity = [
        {
            "type": r["event_type"],
            "description": r["description"],
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in _audit_rows
    ]

    return {
        "offers_by_stage": by_stage,
        "total_offers": total_offers,
        "pipelines_launched": pipelines_launched,
        "pipelines_completed": pipelines_completed,
        "pipelines_running": pipelines_running,
        "pipelines_failed": pipelines_failed,
        "total_cvs_scored": total_cvs_scored,
        "average_matching_score": candidate_stats["average_matching_score"],
        "unassigned_offers_count": by_stage.get("open", 0),
        "candidates_seen": candidate_stats["candidates_seen"],
        "candidates_shortlisted": candidate_stats["candidates_shortlisted"],
        "candidates_in_process": candidate_stats["candidates_in_process"],
        "candidates_hired": candidate_stats["candidates_hired"],
        "top_sourcer": top_sourcer,
        "recent_activity": activity,
    }


@app.get("/api/v1/recruiter/kpis")
async def recruiter_kpis_endpoint(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    recruiter_id: Optional[str] = None,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Performance KPIs for recruiter dashboard and admin per-recruiter breakdown."""
    from service.recruiter_kpis import get_recruiter_kpis

    if current_user.role == "recruiter":
        scope_id = current_user.sub
    else:
        scope_id = recruiter_id
    try:
        return get_recruiter_kpis(scope_id, date_from=date_from, date_to=date_to)
    except Exception as exc:
        app_logger.warning("recruiter kpis failed: %s", exc)
        raise HTTPException(status_code=503, detail="Indicateurs indisponibles") from exc


# â”€â”€ Offer helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _offer_to_dict(
    offer,
    skills: list | None = None,
    contract_type: dict | None = None,
    experience_range: dict | None = None,
) -> dict:
    if skills is None:
        try:
            skills = fetch_offer_skills(str(offer.id))
        except Exception as exc:
            app_logger.warning("fetch_offer_skills failed for %s: %s", offer.id, exc)
            skills = []
    if contract_type is None:
        contract_type = fetch_contract_type(getattr(offer, "contract_type_id", None) or 1)
    if experience_range is None and getattr(offer, "experience_range_id", None):
        experience_range = fetch_experience_range(offer.experience_range_id)
    return {
        "id": str(offer.id),
        "title": offer.title,
        "description": offer.description,
        "skills": skills,
        "experience_level": offer.experience_level,
        "location": offer.location,
        "salary_range": offer.salary_range,
        "contract_type": contract_type,
        "experience_range": experience_range,
        "status": offer.status,
        "status_id": getattr(offer, "status_id", None),
        "status_code": getattr(offer, "status_code", None),
        "status_label": getattr(offer, "status_label", None),
        "created_by": str(offer.created_by),
        "assigned_to": str(offer.assigned_to) if offer.assigned_to else None,
        "session_id": offer.session_id,
        "offer_sftp_path": offer.offer_sftp_path,
        "source_storage_path": getattr(offer, "source_storage_path", None),
        "source_original_filename": getattr(offer, "source_original_filename", None),
        "source_file_size": getattr(offer, "source_file_size", None),
        "source_sha256": getattr(offer, "source_sha256", None),
        "job_id": offer.job_id,
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
        "updated_at": offer.updated_at.isoformat() if offer.updated_at else None,
    }


def _offer_with_job(
    offer,
    skills: list | None = None,
    contract_type: dict | None = None,
    experience_range: dict | None = None,
) -> dict:
    d = _offer_to_dict(
        offer,
        skills=skills,
        contract_type=contract_type,
        experience_range=experience_range,
    )
    job_info = None
    # Prefer the explicit offerâ†’job link (offer.job_id); fall back to session_id
    # for older offers launched before the link existed.
    job = None
    if getattr(offer, "job_id", None):
        job = get_job(offer.job_id)
    if job is None and offer.session_id:
        job = get_job_by_session_id(offer.session_id)
    if job:
        job_info = {
            "id": job.job_id,
            "status": job.status,
            "stage": job.stage,
            "cv_count": job.cv_count,
            "error_message": job.error_message,
        }
        if job.status in ("succeeded", "completed") and job.session_id:
            matched = _read_matching_candidate_count(job.session_id)
            if matched is not None:
                job_info["matched_count"] = matched
    d["job"] = job_info
    return d


# â”€â”€ CV Bank â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/v1/staging/cv-bank/{profile}")
async def cv_bank_profile(
    profile: str,
    current_user: TokenPayload = Depends(_require_role("sourcer", "recruiter", "admin")),
):
    """
    Read CV metadata from SFTP CV_Theque/{profile}/{seniority}/extracted/*.json.
    Returns titre, annees_experience, first 3 competences per CV.
    Limited to 50 CVs per seniority to avoid SFTP overload.
    """
    import json as _json
    import stat as _stat

    mounted_profile_path = CV_THEQUE_DIR / normalize_profile(profile)
    try:
        if mounted_profile_path.exists() and mounted_profile_path.is_dir():
            result = []
            for seniority_dir in sorted(p for p in mounted_profile_path.iterdir() if p.is_dir()):
                extracted_dir = seniority_dir / "extracted"
                if not extracted_dir.exists():
                    result.append({"name": seniority_dir.name, "cv_count": 0, "cvs": []})
                    continue

                cvs = []
                for json_path in sorted(extracted_dir.glob("*.json"))[:50]:
                    try:
                        data = _json.loads(json_path.read_text(encoding="utf-8"))
                        info = data.get("informations_personnelles", {})
                        profil = data.get("profil_resume", {})
                        comp = data.get("competences", {})
                        all_sk = (comp.get("technologies", []) or []) + (comp.get("methodologies_et_outils", []) or [])
                        skills = [s for s in all_sk if isinstance(s, str)][:3]
                        cvs.append({
                            "filename": json_path.name,
                            "nom_complet": info.get("nom_complet", ""),
                            "titre": info.get("titre", ""),
                            "annees_experience": profil.get("annees_experience", ""),
                            "competences_preview": skills,
                        })
                    except Exception:
                        continue

                result.append({"name": seniority_dir.name, "cv_count": len(cvs), "cvs": cvs})

            return {"profile": profile, "seniorities": result}
    except OSError as exc:
        app_logger.warning("CV_Theque cv-bank read failed path=%s err=%s", mounted_profile_path, exc)
        raise HTTPException(status_code=503, detail="CVtheque locale inaccessible") from exc


# â”€â”€ SFTP / Staging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_VALID_EXTENSIONS = set(_CONFIG["pipeline"]["supported_extensions"])
_VALID_SENIORITIES = {s.lower() for s in _CONFIG["pipeline"]["seniority_levels"]}
_MAX_UPLOAD_BYTES = int(_CONFIG["api"]["staging_upload_max_mb"]) * 1024 * 1024
_WATCHER_STAGING_PATH = os.getenv("WATCHER_STAGING_PATH", "/sftp/cv_tech/files/staging")


class _GoogleDriveImportRequest(PydanticBaseModel):
    file_urls: list[str] = []
    folder_url: Optional[str] = None
    profile: Optional[str] = None
    seniority: Optional[str] = None
    max_files: int = 50


def _staging_target_path(filename: str, profile: Optional[str], seniority: Optional[str]) -> Path:
    try:
        return resolve_staging_upload_path(
            staging_root=Path(_WATCHER_STAGING_PATH),
            filename=_safe_upload_filename(filename),
            profile=profile,
            seniority=seniority,
        )
    except StoragePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _unique_staging_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _write_staging_cv_bytes(
    *,
    filename: str,
    content: bytes,
    profile: Optional[str],
    seniority: Optional[str],
    unique: bool = False,
) -> Path:
    filename = _safe_upload_filename(filename)
    ext = Path(filename).suffix.lower()
    if ext not in _VALID_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporte : {ext or '(aucun)'}. Formats acceptes : .pdf, .docx, .doc",
        )
    if seniority and not profile:
        raise HTTPException(
            status_code=400,
            detail="La seniorite ne peut pas etre definie sans un profil.",
        )
    if seniority and seniority.lower() not in _VALID_SENIORITIES:
        raise HTTPException(status_code=400, detail=f"Seniorite inconnue : {seniority}")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (maximum 10 Mo).")

    try:
        mount_path, _ = atomic_write_staging_upload(
            staging_root=Path(_WATCHER_STAGING_PATH),
            filename=filename,
            source=io.BytesIO(content),
            max_bytes=_MAX_UPLOAD_BYTES,
            profile=profile,
            seniority=seniority,
            unique=unique,
        )
    except StoragePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StagingWriteError as exc:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (maximum 10 Mo).") from exc
    except OSError as exc:
        app_logger.warning("Staging local write unavailable filename=%s err=%s", filename, exc)
        raise HTTPException(status_code=503, detail="Stockage staging local inaccessible.") from exc

    return mount_path


@app.get("/api/v1/staging/profiles")
async def get_staging_profiles(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Return the live profile list read from the mounted CV_Theque."""
    try:
        profiles = sorted(
            entry.name
            for entry in CV_THEQUE_DIR.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
        return {"profiles": profiles}
    except OSError as exc:
        app_logger.warning("CV_Theque profile listing failed path=%s err=%s", CV_THEQUE_DIR, exc)
        raise HTTPException(
            status_code=503,
            detail="CVtheque locale inaccessible. Impossible de recuperer la liste des profils.",
        ) from exc


@app.get("/api/v1/staging/seniorities")
async def get_staging_seniorities(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Return the supported seniority levels for the staging upload UI."""
    return {"seniorities": ["junior", "confirme", "senior", "expert"]}


@app.post("/api/v1/staging/google-drive/import")
async def import_google_drive_cvs(
    body: _GoogleDriveImportRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Import CV PDFs/DOCX/DOC files from Google Drive into the local staging folder."""
    if body.seniority and not body.profile:
        raise HTTPException(status_code=400, detail="La seniorite ne peut pas etre definie sans un profil.")
    if body.seniority and body.seniority.lower() not in _VALID_SENIORITIES:
        raise HTTPException(status_code=400, detail=f"Seniorite inconnue : {body.seniority}")

    requested_files = [url for url in body.file_urls if url and url.strip()]
    max_files = max(1, min(int(body.max_files or 50), 100))

    try:
        drive_files = [get_drive_file_metadata(url) for url in requested_files]
        if body.folder_url:
            drive_files.extend(list_drive_folder_files(body.folder_url, max_files=max_files))
    except GoogleDriveImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    drive_files = dedupe_files(drive_files)[:max_files]
    if not drive_files:
        raise HTTPException(status_code=400, detail="Aucun CV Google Drive compatible trouve.")

    imported: list[dict] = []
    failed: list[dict] = []

    for drive_file in drive_files:
        filename = _safe_upload_filename(drive_file.name)
        ext = Path(filename).suffix.lower()
        if ext not in _VALID_EXTENSIONS:
            failed.append({"filename": filename, "drive_file_id": drive_file.file_id, "error": "Format non supporte"})
            continue
        if drive_file.size and drive_file.size > _MAX_UPLOAD_BYTES:
            failed.append({"filename": filename, "drive_file_id": drive_file.file_id, "error": "Fichier trop volumineux"})
            continue

        try:
            content = download_drive_file(drive_file.file_id, max_bytes=_MAX_UPLOAD_BYTES)
            staging_path = _write_staging_cv_bytes(
                filename=filename,
                content=content,
                profile=body.profile,
                seniority=body.seniority,
                unique=True,
            )
            imported.append({
                "filename": staging_path.name,
                "source_filename": filename,
                "drive_file_id": drive_file.file_id,
                "staging_path": str(staging_path),
                "status": "uploaded",
            })
        except (GoogleDriveImportError, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            failed.append({"filename": filename, "drive_file_id": drive_file.file_id, "error": detail})

    return {
        "status": "completed" if not failed else "partial",
        "imported_count": len(imported),
        "failed_count": len(failed),
        "imported": imported,
        "failed": failed,
    }


@app.post("/api/v1/cv-alignments")
async def create_cv_alignment(
    offer_file: UploadFile = File(...),
    cv_file: UploadFile = File(...),
    language: str = Form("fr"),
    current_user: TokenPayload = Depends(_require_role("sourcer", "recruiter", "admin")),
):
    """Queue a single-CV alignment job without using the CV bank."""
    try:
        offer_name = _safe_upload_filename(offer_file.filename)
        cv_name = _safe_upload_filename(cv_file.filename)
        offer_content = await offer_file.read()
        cv_content = await cv_file.read()
        if not offer_content:
            raise HTTPException(status_code=400, detail="Le fichier d'offre est vide.")
        if not cv_content:
            raise HTTPException(status_code=400, detail="Le fichier CV est vide.")

        alignment_id, offer_path, cv_path = create_alignment_workspace(
            offer_name,
            offer_content,
            cv_name,
            cv_content,
            user_id=current_user.sub,
        )
        worker = threading.Thread(
            target=_run_cv_alignment_worker,
            args=(alignment_id, offer_path, cv_path, language, offer_name, cv_name, current_user.sub),
            daemon=True,
        )
        worker.start()

        app_logger.info(
            "CV alignment queued id=%s user=%s offer=%s cv=%s",
            alignment_id,
            current_user.sub,
            offer_name,
            cv_name,
        )
        return JSONResponse(
            status_code=202,
            content={
                "alignment_id": alignment_id,
                "status": "queued",
                "progress": 5,
                "stage_label": "En attente",
                "status_url": f"/api/v1/cv-alignments/{alignment_id}",
            },
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        app_logger.exception("Unexpected CV alignment queue error")
        raise HTTPException(status_code=500, detail="Erreur lors de l'alignement du CV.")


def _run_cv_alignment_worker(
    alignment_id: str,
    offer_path: Path,
    cv_path: Path,
    language: str,
    offer_name: str,
    cv_name: str,
    user_id: str,
) -> None:
    try:
        write_alignment_status(
            alignment_id,
            {
                "alignment_id": alignment_id,
                "status": "running",
                "progress": 10,
                "stage_label": "DÃ©marrage",
                "user_id": user_id,
                "offer_filename": offer_name,
                "cv_filename": cv_name,
            },
        )

        def report_progress(progress: int, stage_label: str) -> None:
            write_alignment_status(
                alignment_id,
                {
                    "alignment_id": alignment_id,
                    "status": "running",
                    "progress": progress,
                    "stage_label": stage_label,
                    "user_id": user_id,
                    "offer_filename": offer_name,
                    "cv_filename": cv_name,
                },
            )

        result = align_cv_to_offer(
            offer_path,
            cv_path,
            language=language,
            alignment_id=alignment_id,
            source_offer_name=offer_name,
            source_cv_name=cv_name,
            progress_callback=report_progress,
        )
        write_alignment_status(
            alignment_id,
            {
                "alignment_id": alignment_id,
                "status": "succeeded",
                "progress": 100,
                "stage_label": "PrÃªt Ã  tÃ©lÃ©charger",
                "user_id": user_id,
                "filename": result.filename,
                "download_url": f"/api/v1/cv-alignments/{alignment_id}/download",
                "offer_chars": result.offer_chars,
                "cv_chars": result.cv_chars,
                "offer_filename": offer_name,
                "cv_filename": cv_name,
            },
        )
        app_logger.info(
            "CV alignment created id=%s user=%s offer=%s cv=%s",
            alignment_id,
            user_id,
            offer_name,
            cv_name,
        )
    except Exception as exc:
        app_logger.exception("CV alignment worker failed id=%s", alignment_id)
        try:
            write_alignment_status(
                alignment_id,
                {
                    "alignment_id": alignment_id,
                    "status": "failed",
                    "progress": 100,
                    "stage_label": "Ã‰chec",
                    "user_id": user_id,
                    "error": _friendly_cv_alignment_error(exc),
                    "offer_filename": offer_name,
                    "cv_filename": cv_name,
                },
            )
        except Exception:
            app_logger.exception("Could not write failed CV alignment status id=%s", alignment_id)


def _friendly_cv_alignment_error(exc: Exception) -> str:
    message = str(exc) or ""
    lowered = message.lower()
    if "more credits" in lowered or "402" in lowered or "crÃ©dits openrouter" in lowered or "credits openrouter" in lowered:
        return (
            "CrÃ©dits OpenRouter insuffisants pour gÃ©nÃ©rer ce CV. "
            "Ajoutez des crÃ©dits ou utilisez un modÃ¨le moins coÃ»teux, puis relancez."
        )
    if "json valide" in lowered or "valid json" in lowered:
        return "Le modÃ¨le n'a pas retournÃ© un format exploitable. Relancez avec un CV plus court ou un modÃ¨le plus fiable."
    if "timed out" in lowered or "timeout" in lowered:
        return "L'alignement prend plus de temps que prÃ©vu. RÃ©essayez avec un CV plus court ou un modÃ¨le plus rapide."
    return "Erreur lors de l'alignement du CV. RÃ©essayez dans quelques instants."


@app.get("/api/v1/cv-alignments/recent")
async def get_recent_cv_alignments(
    limit: int = 5,
    current_user: TokenPayload = Depends(_require_role("sourcer", "recruiter", "admin")),
):
    """Return the latest CV alignment jobs visible to the current user."""
    include_all = current_user.role == "admin"
    return {
        "alignments": list_recent_alignments(
            user_id=current_user.sub,
            limit=limit,
            include_all=include_all,
        )
    }


@app.get("/api/v1/cv-alignments/{alignment_id}")
async def get_cv_alignment_status(
    alignment_id: str,
    current_user: TokenPayload = Depends(_require_role("sourcer", "recruiter", "admin")),
):
    """Return status for a queued CV alignment."""
    try:
        status = read_alignment_status(alignment_id)
        _ensure_alignment_access(status, current_user)
        return status
    except ValueError:
        raise HTTPException(status_code=404, detail="Alignement introuvable")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Alignement introuvable")


@app.get("/api/v1/cv-alignments/{alignment_id}/download")
async def download_cv_alignment(
    alignment_id: str,
    current_user: TokenPayload = Depends(_require_role("sourcer", "recruiter", "admin")),
):
    """Download a generated aligned CV."""
    try:
        status = read_alignment_status(alignment_id)
        _ensure_alignment_access(status, current_user)
        output_path = resolve_alignment_download(alignment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="CV alignÃ© introuvable")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="CV alignÃ© introuvable")
    media_type = "application/pdf" if output_path.suffix.lower() == ".pdf" else "text/html"
    return FileResponse(output_path, filename=output_path.name, media_type=media_type)


def _ensure_alignment_access(status: dict, current_user: TokenPayload) -> None:
    owner = status.get("user_id")
    if owner and owner != current_user.sub and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="Alignement introuvable")


@app.post("/api/v1/staging/upload")
async def staging_upload(
    file: UploadFile = File(...),
    profile: Optional[str] = Form(None),
    seniority: Optional[str] = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Upload one CV file to the SFTP staging folder. Called once per file for per-file progress."""
    filename = _safe_upload_filename(file.filename)  # S-CRIT-3 D
    ext = Path(filename).suffix.lower()
    if ext not in _VALID_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supportÃ© : {ext or '(aucun)'}. Formats acceptÃ©s : .pdf, .docx, .doc",
        )

    if seniority and not profile:
        raise HTTPException(
            status_code=400,
            detail="La sÃ©nioritÃ© ne peut pas Ãªtre dÃ©finie sans un profil.",
        )


    if seniority and seniority.lower() not in _VALID_SENIORITIES:
        raise HTTPException(status_code=400, detail=f"SÃ©nioritÃ© inconnue : {seniority}")

    try:
        mount_path, _ = atomic_write_staging_upload(
            staging_root=Path(_WATCHER_STAGING_PATH),
            filename=filename,
            source=file.file,
            max_bytes=_MAX_UPLOAD_BYTES,
            profile=profile,
            seniority=seniority,
            unique=True,
        )
    except StoragePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StagingWriteError as exc:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (maximum 10 Mo).") from exc
    except OSError as exc:
        app_logger.warning("Staging local write unavailable filename=%s err=%s", filename, exc)
        raise HTTPException(status_code=503, detail="Stockage staging local inaccessible.") from exc

    return {"filename": mount_path.name, "staging_path": str(mount_path), "status": "uploaded"}


# ============================================================================
# ADMIN SPACE (Workstream 3) â€” all endpoints require role: admin
# ============================================================================

_VALID_USER_ROLES = {"sourcer", "recruiter", "admin"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _AdminCreateUser(PydanticBaseModel):
    email: str
    full_name: str
    role: str
    password: str


class _AdminUpdateUser(PydanticBaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = None


def _role_label(role: str) -> str:
    return {"recruiter": "Recruteur", "sourcer": "Sourceur", "admin": "Administrateur"}.get(role, role)


def _user_to_admin_dict(u) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@app.get("/api/v1/admin/users")
async def admin_list_users(
    role: Optional[str] = None,
    active: Optional[bool] = None,
    current_user: TokenPayload = Depends(_require_role("admin")),
):
    """List all users, optionally filtered by ?role= and/or ?active=."""
    if role is not None and role not in _VALID_USER_ROLES:
        raise HTTPException(status_code=400, detail="RÃ´le invalide.")
    users = list_users(role=role, active=active)
    return {"users": [_user_to_admin_dict(u) for u in users]}


@app.post("/api/v1/admin/users", status_code=201)
async def admin_create_user(
    body: _AdminCreateUser,
    current_user: TokenPayload = Depends(_require_role("admin")),
):
    """Create a new user (same logic as the seed script)."""
    email = (body.email or "").strip().lower()
    full_name = (body.full_name or "").strip()
    if not email or not full_name or not body.password:
        raise HTTPException(status_code=400, detail="Tous les champs sont requis.")
    if body.role not in _VALID_USER_ROLES:
        raise HTTPException(status_code=400, detail="RÃ´le invalide.")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractÃ¨res.")
    if user_exists(email):
        raise HTTPException(status_code=409, detail="Un utilisateur avec cet email existe dÃ©jÃ .")
    user = create_user(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    app_logger.info(f"Admin {current_user.sub} created user {email} ({body.role})")
    _admin = get_user_by_id(current_user.sub)
    audit_store.log_event(
        event_type="user_created",
        description=f"Utilisateur {full_name} ({_role_label(body.role)}) crÃ©Ã©",
        actor_id=current_user.sub,
        actor_name=_admin.full_name if _admin else None,
        target_id=str(user.id),
        target_type="user",
    )
    return _user_to_admin_dict(user)


@app.patch("/api/v1/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    body: _AdminUpdateUser,
    current_user: TokenPayload = Depends(_require_role("admin")),
):
    """Update a user's name/email/role/active flag.

    Cannot change own role, own email, or deactivate self.
    """
    if not _UUID_RE.match(user_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    is_self = str(target.id) == current_user.sub

    # â”€â”€ Email change validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    new_email: Optional[str] = None
    if body.email is not None:
        new_email = body.email.strip().lower()
        if not _EMAIL_RE.match(new_email):
            raise HTTPException(status_code=400, detail="Format d'email invalide.")
        if new_email != target.email.lower():
            if is_self:
                raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre email.")
            if user_exists(new_email):
                raise HTTPException(status_code=409, detail="Cet email est dÃ©jÃ  utilisÃ©")
        else:
            new_email = None  # unchanged â€” skip the SET

    if body.role is not None:
        if body.role not in _VALID_USER_ROLES:
            raise HTTPException(status_code=400, detail="RÃ´le invalide.")
        if is_self and body.role != target.role:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas modifier votre propre rÃ´le.")
    if body.is_active is False and is_self:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas dÃ©sactiver votre propre compte.")

    updated = update_user(
        user_id,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
        email=new_email,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    app_logger.info(f"Admin {current_user.sub} updated user {user_id}")

    _admin = get_user_by_id(current_user.sub)
    _actor_name = _admin.full_name if _admin else None
    # Activation toggle gets its own dedicated audit event type.
    if body.is_active is False and target.is_active:
        audit_store.log_event(
            event_type="user_deactivated",
            description=f"Compte de {updated.full_name} dÃ©sactivÃ©",
            actor_id=current_user.sub, actor_name=_actor_name,
            target_id=str(updated.id), target_type="user",
        )
    elif body.is_active is True and not target.is_active:
        audit_store.log_event(
            event_type="user_reactivated",
            description=f"Compte de {updated.full_name} rÃ©activÃ©",
            actor_id=current_user.sub, actor_name=_actor_name,
            target_id=str(updated.id), target_type="user",
        )
    else:
        audit_store.log_event(
            event_type="user_updated",
            description=f"Compte de {updated.full_name} mis Ã  jour",
            actor_id=current_user.sub, actor_name=_actor_name,
            target_id=str(updated.id), target_type="user",
        )
    return _user_to_admin_dict(updated)


@app.delete("/api/v1/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    current_user: TokenPayload = Depends(_require_role("admin")),
):
    """Soft-delete a user (sets deleted_at). Cannot delete self."""
    if not _UUID_RE.match(user_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if str(user_id) == current_user.sub:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte.")
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    soft_delete_user(user_id)
    app_logger.info(f"Admin {current_user.sub} deleted user {user_id}")
    _admin = get_user_by_id(current_user.sub)
    audit_store.log_event(
        event_type="user_deleted",
        description=f"Compte de {target.full_name} supprimÃ©",
        actor_id=current_user.sub,
        actor_name=_admin.full_name if _admin else None,
        target_id=str(target.id), target_type="user",
    )
    return {"status": "deleted", "user_id": str(user_id)}


@app.get("/api/v1/admin/stats")
async def admin_stats(current_user: TokenPayload = Depends(_require_role("admin"))):
    """System-wide statistics for the admin dashboard."""
    user_stats = get_user_stats()
    offer_status = get_offer_status_counts()
    job_counts = get_job_status_counts()
    return {
        "users": user_stats,
        "offers": {
            "total": sum(offer_status.values()),
            "by_status": offer_status,
        },
        "pipeline_jobs": job_counts,
        "cvs_in_cvtheque": None,  # requires SFTP â€” intentionally not fetched
    }


@app.get("/api/v1/admin/insights")
async def admin_insights(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: TokenPayload = Depends(_require_role("admin")),
):
    """CEO dashboard â€” aggregated platform insights with optional date range."""
    from service.admin_insights import get_admin_insights

    try:
        return get_admin_insights(date_from=date_from, date_to=date_to)
    except Exception as exc:
        app_logger.error("admin insights failed: %s", exc)
        raise HTTPException(status_code=503, detail="Insights indisponibles") from exc


# â”€â”€ CANDIDATES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_DECISION_LABELS_FR = {
    "pending": "En attente",
    "shortlisted": "PrÃ©sÃ©lectionnÃ©",
    "contacted": "ContactÃ©",
    "interviewed": "InterviewÃ©",
    "offered": "Offre faite",
    "hired": "RecrutÃ©",
    "rejected": "RefusÃ©",
}


def _assert_offer_pipeline_access(offer_id: str, current_user: TokenPayload):
    """Sourcer assigned to the offer OR recruiter who created it (admin: any)."""
    offer = get_offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if current_user.role == "admin":
        return offer
    if current_user.role == "recruiter" and str(offer.created_by) == current_user.sub:
        return offer
    if current_user.role == "sourcer" and str(offer.assigned_to) == current_user.sub:
        return offer
    raise HTTPException(status_code=403, detail="AccÃ¨s refusÃ©")


def _assert_appearance_note_access(appearance_id: str, current_user: TokenPayload) -> dict:
    try:
        appearance = store_get_appearance_by_id(appearance_id)
    except Exception as exc:
        app_logger.warning("get_appearance_by_id failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not appearance:
        raise HTTPException(status_code=404, detail="Apparition introuvable")
    _assert_offer_pipeline_access(str(appearance["offer_id"]), current_user)
    return appearance


def _normalize_appearance_notes(row: dict) -> dict:
    """Expose sourcer_note / recruiter_note; fall back to legacy decision_notes."""
    legacy = (row.get("decision_notes") or "").strip()
    sourcer = (row.get("sourcer_note") or "").strip()
    recruiter = (row.get("recruiter_note") or "").strip()
    if legacy and not sourcer and not recruiter:
        row["recruiter_note"] = legacy
    else:
        row["sourcer_note"] = sourcer or None
        row["recruiter_note"] = recruiter or None
    return row


def _enrich_appearances_with_flags(rows: list) -> list:
    """Attach per-candidate active unreliability flag to each appearance row."""
    if not rows:
        return rows
    candidate_ids = list({str(r["candidate_id"]) for r in rows if r.get("candidate_id")})
    try:
        flags_map = store_get_active_unreliability_flags_bulk(candidate_ids)
    except Exception as exc:
        app_logger.warning("get_active_unreliability_flags_bulk failed: %s", exc)
        flags_map = {}
    for r in rows:
        cid = str(r.get("candidate_id") or "")
        r["unreliability_flag"] = store_format_unreliability_flag(flags_map.get(cid))
    return rows


def _offer_appearances_response(offer_id: str, offer) -> dict:
    try:
        store_sync_appearances_for_offer(offer_id)
        rows = store_get_offer_appearances(offer_id)
        if not rows:
            store_backfill_appearances()
            store_sync_appearances_for_offer(offer_id)
            rows = store_get_offer_appearances(offer_id)
    except Exception as exc:
        app_logger.warning("get_offer_appearances failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    for r in rows:
        _normalize_appearance_notes(r)
        r["decision_label"] = _DECISION_LABELS_FR.get(r.get("decision", ""), r.get("decision"))
    _enrich_appearances_with_flags(rows)
    return {"offer_id": offer_id, "offer_title": offer.title, "candidates": rows}

_SOURCER_NOTE_TYPES = {"general", "behavioral", "availability"}
_SOURCER_PATCH_FIELDS = {"open_to_work", "availability_date"}


def _load_cv_summary(cv_sftp_path: Optional[str]) -> dict:
    """Read extracted CV JSON from the mounted CV_Theque path (best-effort).

    Never raises â€” a stale/disconnected sshfs mount (Errno 107) must not
    break list/detail endpoints that already have DB-backed candidate data.
    """
    if not cv_sftp_path:
        return {}
    path = Path(cv_sftp_path)
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        app_logger.debug("cv_summary mount/path error path=%s err=%s", cv_sftp_path, exc)
        return {}
    except Exception:
        return {}
    profil = data.get("profil_resume") or {}
    competences = data.get("competences") or {}
    techs = competences.get("technologies") or []
    tools = competences.get("methodologies_et_outils") or []
    skills: list[str] = []
    for item in techs + tools:
        if isinstance(item, str):
            skills.append(item)
        elif isinstance(item, dict):
            skills.append(item.get("nom") or item.get("name") or str(item))
    exps = data.get("experiences_professionnelles") or []
    resume = profil.get("resume") or profil.get("description") or profil.get("profil")
    return {
        "skills": skills[:15],
        "experiences_count": len(exps),
        "titre": (data.get("informations_personnelles") or {}).get("titre"),
        "resume": resume,
    }


def _build_cv_summary(cand: dict) -> dict:
    """Merge SFTP CV JSON with DB-backed candidate fields (Action 238)."""
    summary = _load_cv_summary(cand.get("cv_sftp_path"))
    db_skills = cand.get("skills") or []
    if db_skills and not summary.get("skills"):
        summary["skills"] = db_skills
    if not summary.get("titre"):
        summary["titre"] = cand.get("profile_label_fr") or cand.get("profile")
    db_years = (cand.get("annees_experience") or "").strip()
    if db_years:
        summary["annees_experience"] = db_years
    return summary


class CandidatePatchBody(PydanticBaseModel):
    open_to_work: Optional[bool] = None
    availability_date: Optional[str] = None
    current_salary: Optional[float] = None
    expected_salary: Optional[float] = None
    onboarded: Optional[bool] = None
    onboarding_date: Optional[str] = None


class CandidateNoteBody(PydanticBaseModel):
    content: str
    note_type: str = "general"


class CandidateNotePatchBody(PydanticBaseModel):
    content: str
    note_type: str = "general"


class AppearanceDecisionBody(PydanticBaseModel):
    decision: str
    decision_notes: Optional[str] = None


class AppearancePhaseStatusBody(PydanticBaseModel):
    phase: str
    status_code: str
    flag_reason: Optional[str] = None


class UnreliabilityResolveBody(PydanticBaseModel):
    resolved_reason: str


class AppearanceNoteBody(PydanticBaseModel):
    note: str = ""


@app.get("/api/v1/candidates")
async def list_candidates_endpoint(
    request: Request,
    profile: Optional[str] = None,
    seniority: Optional[str] = None,
    open_to_work: Optional[bool] = None,
    search: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Paginated list of candidates with latest matching score."""
    check_rate_limit(request)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    if score_min is not None:
        score_min = max(0.0, min(100.0, score_min))
    if score_max is not None:
        score_max = max(0.0, min(100.0, score_max))
    if score_min is not None and score_max is not None and score_min > score_max:
        raise HTTPException(status_code=400, detail="score_min must be <= score_max")
    try:
        result = store_list_candidates(
            profile=profile,
            seniority=seniority,
            open_to_work=open_to_work,
            search=search,
            score_min=score_min,
            score_max=score_max,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        app_logger.warning("list_candidates failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    for c in result.get("candidates") or []:
        if c.get("latest_decision"):
            c["latest_decision_label"] = _DECISION_LABELS_FR.get(c["latest_decision"], c["latest_decision"])
        db_skills = [s["name"] for s in (c.get("skills") or []) if s.get("name")]
        if db_skills:
            c["top_skills"] = db_skills[:3]
        elif c.get("cv_sftp_path"):
            summary = _load_cv_summary(c.get("cv_sftp_path"))
            c["top_skills"] = (summary.get("skills") or [])[:3]
        else:
            c["top_skills"] = []
    return result


@app.get("/api/v1/candidates/{candidate_id}")
async def get_candidate_endpoint(
    request: Request,
    candidate_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Full candidate profile with notes, offer history and CV summary."""
    check_rate_limit(request)
    try:
        cand = store_get_candidate(candidate_id)
    except Exception as exc:
        app_logger.warning("get_candidate failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not cand:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    appearances = store_get_appearances(candidate_id)
    if not appearances:
        try:
            store_backfill_appearances()
        except Exception as exc:
            app_logger.debug("appearance backfill skipped: %s", exc)
        appearances = store_get_appearances(candidate_id)
    notes = store_get_notes(candidate_id)
    for a in appearances:
        a["decision_label"] = _DECISION_LABELS_FR.get(a.get("decision", ""), a.get("decision"))
        total = int(a.get("total_offer_skills") or 0)
        matching = int(a.get("matching_skills_count") or 0)
        a["match_percentage"] = round(100.0 * matching / total, 1) if total > 0 else None
    _enrich_appearances_with_flags(appearances)
    active_flag = None
    try:
        active_flag = store_format_unreliability_flag(store_get_active_unreliability_flag(candidate_id))
    except Exception as exc:
        app_logger.warning("get_active_unreliability_flag failed: %s", exc)
    return {
        "candidate": cand,
        "notes": notes,
        "offer_appearances": appearances,
        "cv_summary": _build_cv_summary(cand),
        "unreliability_flag": active_flag,
    }


@app.patch("/api/v1/candidates/{candidate_id}")
async def patch_candidate_endpoint(
    candidate_id: str,
    body: CandidatePatchBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update candidate fields â€” sourcer: availability only; recruiter/admin: all."""
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Aucun champ Ã  mettre Ã  jour")
    if current_user.role == "sourcer":
        invalid = set(fields) - _SOURCER_PATCH_FIELDS
        if invalid:
            raise HTTPException(
                status_code=403,
                detail="Le sourcer ne peut modifier que open_to_work et availability_date",
            )
    try:
        updated = store_update_candidate(candidate_id, fields)
    except Exception as exc:
        app_logger.warning("update_candidate failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    return {"candidate": updated}


@app.post("/api/v1/candidates/{candidate_id}/notes", status_code=201)
async def add_candidate_note_endpoint(
    candidate_id: str,
    body: CandidateNoteBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Add a note on a candidate profile."""
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Le contenu de la note est requis")
    note_type = body.note_type or "general"
    if current_user.role == "sourcer" and note_type not in _SOURCER_NOTE_TYPES:
        raise HTTPException(
            status_code=403,
            detail="Types de note autorisÃ©s pour le sourcer : general, behavioral, availability",
        )
    user = get_user_by_id(current_user.sub)
    author_name = user.full_name if user else current_user.email
    try:
        if not store_get_candidate(candidate_id):
            raise HTTPException(status_code=404, detail="Candidat introuvable")
        note = store_add_note(
            candidate_id=candidate_id,
            author_id=current_user.sub,
            author_name=author_name,
            author_role=current_user.role,
            content=content,
            note_type=note_type,
        )
    except HTTPException:
        raise
    except Exception as exc:
        app_logger.warning("add_note failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    return {"note": note}


@app.patch("/api/v1/candidates/{candidate_id}/notes/{note_id}")
async def patch_candidate_note_endpoint(
    candidate_id: str,
    note_id: str,
    body: CandidateNotePatchBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update a note â€” author only."""
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Le contenu de la note est requis")
    note_type = body.note_type or "general"
    if current_user.role == "sourcer" and note_type not in _SOURCER_NOTE_TYPES:
        raise HTTPException(
            status_code=403,
            detail="Types de note autorisÃ©s pour le sourcer : general, behavioral, availability",
        )
    try:
        existing = store_get_note(note_id)
        if not existing or str(existing.get("candidate_id")) != str(candidate_id):
            raise HTTPException(status_code=404, detail="Note introuvable")
        if str(existing.get("author_id")) != str(current_user.sub):
            raise HTTPException(status_code=403, detail="Seul l'auteur peut modifier cette note")
        updated = store_update_note(note_id, content, note_type)
    except HTTPException:
        raise
    except Exception as exc:
        app_logger.warning("update_note failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Note introuvable")
    return {"note": updated}


@app.delete("/api/v1/candidates/{candidate_id}/notes/{note_id}", status_code=204)
async def delete_candidate_note_endpoint(
    candidate_id: str,
    note_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Delete a note â€” author or admin."""
    try:
        existing = store_get_note(note_id)
        if not existing or str(existing.get("candidate_id")) != str(candidate_id):
            raise HTTPException(status_code=404, detail="Note introuvable")
        is_author = str(existing.get("author_id")) == str(current_user.sub)
        is_admin = current_user.role == "admin"
        if not is_author and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Seul l'auteur ou un administrateur peut supprimer cette note",
            )
        if not store_delete_note(note_id):
            raise HTTPException(status_code=404, detail="Note introuvable")
    except HTTPException:
        raise
    except Exception as exc:
        app_logger.warning("delete_note failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc


@app.patch("/api/v1/candidates/appearances/{appearance_id}/note")
async def patch_appearance_note_endpoint(
    appearance_id: str,
    body: AppearanceNoteBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update offer-scoped note on a candidate appearance (sourcer or recruiter)."""
    _assert_appearance_note_access(appearance_id, current_user)
    if current_user.role == "sourcer":
        note_role = "sourcer"
    elif current_user.role in ("recruiter", "admin"):
        note_role = "recruiter"
    else:
        raise HTTPException(status_code=403, detail="AccÃ¨s refusÃ©")
    try:
        updated = store_update_appearance_note(appearance_id, body.note, note_role)
    except Exception as exc:
        app_logger.warning("update_appearance_note failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Apparition introuvable")
    updated["decision_label"] = _DECISION_LABELS_FR.get(updated.get("decision", ""), updated.get("decision"))
    return {"appearance": updated}


@app.get("/api/v1/candidates/{candidate_id}/offer-history")
async def get_candidate_offer_history_endpoint(
    candidate_id: str,
    exclude_offer_id: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Other offer appearances for a candidate (excludes current offer when requested)."""
    try:
        rows = store_get_candidate_offer_history(candidate_id, exclude_offer_id=exclude_offer_id)
    except Exception as exc:
        app_logger.warning("get_candidate_offer_history failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    history = []
    for r in rows:
        history.append({
            "offer_id": r.get("offer_id"),
            "offer_title": r.get("offer_title"),
            "offer_status": r.get("offer_status"),
            "matching_score": r.get("matching_score"),
            "final_score": r.get("final_score"),
            "decision": r.get("decision"),
            "decision_label": _DECISION_LABELS_FR.get(r.get("decision", ""), r.get("decision")),
            "created_at": r.get("created_at"),
            "recruiter_id": str(r["recruiter_id"]) if r.get("recruiter_id") else None,
            "recruiter_name": r.get("recruiter_name"),
            "sourcer_name": r.get("sourcer_name"),
        })
    return history


@app.patch("/api/v1/candidates/appearances/{appearance_id}")
async def patch_appearance_decision_endpoint(
    appearance_id: str,
    body: AppearanceDecisionBody,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Update hiring decision on an offer appearance."""
    valid_decisions = set(_DECISION_LABELS_FR.keys())
    if body.decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"DÃ©cision invalide. Valeurs : {', '.join(sorted(valid_decisions))}")
    try:
        updated = store_update_decision(
            appearance_id=appearance_id,
            decision=body.decision,
            decision_notes=body.decision_notes,
            decision_by=current_user.sub,
        )
    except Exception as exc:
        app_logger.warning("update_decision failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Apparition introuvable")
    updated["decision_label"] = _DECISION_LABELS_FR.get(updated.get("decision", ""), updated.get("decision"))
    return {"appearance": updated}


def _assert_appearance_status_access(
    appearance: dict,
    phase: str,
    current_user: TokenPayload,
) -> None:
    offer_id = str(appearance["offer_id"])
    offer = get_offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if phase == "matching":
        if current_user.role == "admin":
            return
        if current_user.role == "recruiter" and str(offer.created_by) == current_user.sub:
            return
        if current_user.role == "sourcer" and str(offer.assigned_to) == current_user.sub:
            return
        raise HTTPException(status_code=403, detail="AccÃ¨s refusÃ©")
    if phase in ("final", "format"):
        if current_user.role == "admin":
            return
        if current_user.role == "recruiter" and str(offer.created_by) == current_user.sub:
            return
        raise HTTPException(status_code=403, detail="AccÃ¨s refusÃ©")
    raise HTTPException(status_code=400, detail="Phase invalide")


def _assert_phase_available(offer, phase: str) -> None:
    status_id = int(offer.status_id or 0)
    min_status = {"matching": 4, "final": 5, "format": 6}.get(phase)
    if min_status is None:
        raise HTTPException(status_code=400, detail="Phase invalide")
    if status_id < min_status:
        raise HTTPException(
            status_code=400,
            detail="Cette Ã©tape n'est pas encore disponible pour cette offre.",
        )


@app.patch("/api/v1/candidates/appearances/{appearance_id}/status")
async def patch_appearance_status_endpoint(
    appearance_id: str,
    body: AppearancePhaseStatusBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update matching/final/format phase status on an offer appearance."""
    phase = (body.phase or "").strip().lower()
    status_code = (body.status_code or "").strip()
    if phase not in ("matching", "final", "format"):
        raise HTTPException(status_code=400, detail="Phase invalide")
    if not status_code:
        raise HTTPException(status_code=400, detail="Statut requis")

    try:
        appearance = store_get_appearance_by_id(appearance_id)
    except Exception as exc:
        app_logger.warning("get_appearance_by_id failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not appearance:
        raise HTTPException(status_code=404, detail="Apparition introuvable")

    offer = get_offer_by_id(str(appearance["offer_id"]))
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    _assert_phase_available(offer, phase)
    _assert_appearance_status_access(appearance, phase, current_user)

    if phase == "format" and status_code == "non_integre":
        flag_reason = (body.flag_reason or "").strip()
        if not flag_reason:
            raise HTTPException(
                status_code=400,
                detail="La raison est requise pour le statut Â« Non intÃ©grÃ© Â».",
            )

    try:
        updated = store_update_appearance_status(
            appearance_id, phase, status_code, changed_by=current_user.sub
        )
    except Exception as exc:
        app_logger.warning("update_appearance_status failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not updated:
        raise HTTPException(status_code=400, detail="Statut invalide")

    if phase == "format" and status_code == "non_integre":
        user = get_user_by_id(current_user.sub)
        author_name = user.full_name if user else current_user.email
        try:
            store_create_unreliability_flag(
                candidate_id=str(appearance["candidate_id"]),
                offer_id=str(appearance["offer_id"]),
                appearance_id=appearance_id,
                reason=(body.flag_reason or "").strip(),
                flagged_by=current_user.sub,
                flagged_by_name=author_name,
            )
            audit_store.log_event(
                event_type="candidate_flagged_unreliable",
                description=f"Candidat signalÃ© comme non fiable â€” {author_name}",
                actor_id=current_user.sub,
                actor_name=author_name,
            )
        except Exception as exc:
            app_logger.warning("create_unreliability_flag failed: %s", exc)
            raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc

    flag = store_format_unreliability_flag(
        store_get_active_unreliability_flag(str(appearance["candidate_id"]))
    )
    updated["unreliability_flag"] = flag
    return {"appearance": updated}


@app.get("/api/v1/candidates/{candidate_id}/unreliability-flag")
async def get_candidate_unreliability_flag_endpoint(
    candidate_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Active (unresolved) unreliability flag for a candidate, if any."""
    try:
        flag = store_get_active_unreliability_flag(candidate_id)
    except Exception as exc:
        app_logger.warning("get_active_unreliability_flag failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    return {"flag": store_format_unreliability_flag(flag)}


@app.post("/api/v1/candidates/{candidate_id}/unreliability-flag/{flag_id}/resolve")
async def resolve_candidate_unreliability_flag_endpoint(
    candidate_id: str,
    flag_id: str,
    body: UnreliabilityResolveBody,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """Mark an unreliability flag as resolved."""
    resolved_reason = (body.resolved_reason or "").strip()
    if not resolved_reason:
        raise HTTPException(status_code=400, detail="La raison de rÃ©solution est requise.")
    try:
        flag = store_get_unreliability_flag_by_id(flag_id)
    except Exception as exc:
        app_logger.warning("get_unreliability_flag_by_id failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not flag or str(flag.get("candidate_id")) != candidate_id:
        raise HTTPException(status_code=404, detail="Signalement introuvable")
    if flag.get("resolved_at"):
        raise HTTPException(status_code=400, detail="Signalement dÃ©jÃ  rÃ©solu")
    try:
        updated = store_resolve_unreliability_flag(flag_id, current_user.sub, resolved_reason)
    except Exception as exc:
        app_logger.warning("resolve_unreliability_flag failed: %s", exc)
        raise HTTPException(status_code=503, detail="Base candidats indisponible") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Signalement introuvable")
    return {"flag": store_format_unreliability_flag(updated)}


@app.get("/api/v1/offers/{offer_id}/appearances")
async def get_offer_appearances_endpoint(
    request: Request,
    offer_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Offer appearances with decision_notes â€” sourcer (assigned) or recruiter (owner)."""
    check_rate_limit(request)
    offer = _assert_offer_pipeline_access(offer_id, current_user)
    return _offer_appearances_response(offer_id, offer)


@app.get("/api/v1/offers/{offer_id}/candidates")
async def get_offer_candidates_endpoint(
    request: Request,
    offer_id: str,
    current_user: TokenPayload = Depends(_require_role("recruiter", "admin")),
):
    """All candidates who appeared in this offer, sorted by rank."""
    check_rate_limit(request)
    offer = get_offer_for_recruiter(offer_id, current_user.sub)
    if not offer and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if current_user.role == "admin" and not offer:
        offer = get_offer_by_id(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return _offer_appearances_response(offer_id, offer)


@app.get("/api/v1/admin/activity")
async def admin_activity(
    event_type: Optional[str] = None,
    current_user: TokenPayload = Depends(_require_role("admin")),
):
    """Last 20 system events, sourced from the audit.activity_log table."""
    rows = audit_store.get_recent_activity(limit=20, event_type=event_type)
    return {
        "events": [
            {
                "type": r["event_type"],
                "description": r["description"],
                "user": r["actor_name"],
                "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }





