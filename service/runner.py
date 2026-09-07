from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import traceback
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4
from urllib import request
from urllib.error import URLError, HTTPError

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config_yaml.yaml"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CONFIG = yaml.safe_load(_f)

from service.config import (
    API_JOBS_DIR,
    CURRENT_DIR,
    ARCHIVE_DIR,
    CV_THEQUE_DIR,
    safe_relpath,
    write_cv_source_marker,
    INGEST_SCRIPT,
    MAIN_SCRIPT,
    PIPELINE_PG_DSN,
    TRANSFORMER_SCRIPT,
    PROJECT_ROOT,
    N8N_MATCHING_WEBHOOK_URL,
    N8N_FINAL_WEBHOOK_URL,
    N8N_PIPELINE_WEBHOOK_URL,
    ENABLE_PG_INGEST,
)
from service.job_store import create_job, get_job, update_job
from service.models import PipelineArtifacts, PipelineJob
from service.logging_config import app_logger
from service.cv_storage import normalize_profile, normalize_seniority
from service.offer_parser import get_offer_parser
from service.seniority_folders import resolve_seniority_folders, build_matching_experience_context

# Import offer extraction functions for Offer Only mode
try:
    from script.offer_extractor import extract_offer_text, save_offer_to_session
    OFFER_EXTRACTION_AVAILABLE = True
except ImportError:
    OFFER_EXTRACTION_AVAILABLE = False
    app_logger.warning("Offer extraction functions not available - offers will be copied as-is")


def _write_to_log(log_path: Path, message: str) -> None:
    """Write message to log file with timestamp."""
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        # Fallback to app_logger if file writing fails
        app_logger.error(f"Failed to write to log file {log_path}: {str(e)}")


def _write_to_stdout_log(log_path: Path, message: str) -> None:
    """Write message to stdout log file."""
    _write_to_log(log_path, message)


def _write_to_stderr_log(log_path: Path, message: str) -> None:
    """Write message to stderr log file."""
    _write_to_log(log_path, message)


def create_job_workspace(job_id: str) -> dict[str, Path]:
    job_dir = API_JOBS_DIR / job_id
    inputs_dir = job_dir / "inputs"
    offer_dir = inputs_dir / "offer"
    cvs_dir = inputs_dir / "cvs"
    logs_dir = job_dir / "logs"

    offer_dir.mkdir(parents=True, exist_ok=True)
    cvs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    return {
        "job_dir": job_dir,
        "inputs_dir": inputs_dir,
        "offer_dir": offer_dir,
        "cvs_dir": cvs_dir,
        "logs_dir": logs_dir,
    }


def create_job_record(
    session_id: str,
    offer_filename: str,
    cv_count: int,
    archive_enabled: bool,
    artifacts: PipelineArtifacts,
) -> PipelineJob:
    job = PipelineJob(
        job_id=str(uuid4()),
        session_id=session_id,
        status="queued",
        stage="preparing_inputs",
        created_at=datetime.utcnow(),
        offer_filename=offer_filename,
        cv_count=cv_count,
        archive_enabled=archive_enabled,
        artifacts=artifacts,
    )
    create_job(job)
    return job


def _write_metadata(job_dir: Path, payload: dict) -> None:
    metadata_path = job_dir / "metadata.json"
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# Conventional exit code used when a subprocess is killed for exceeding its
# wall-clock timeout (mirrors the GNU `timeout` utility).
_TIMEOUT_EXIT_CODE = 124


def _max_subprocess_timeout_seconds() -> int:
    return int(_CONFIG.get("pipeline", {}).get("max_subprocess_timeout_seconds", 1800))


def _run_subprocess(
    command: list[str],
    cwd: Path,
    log_stdout: Path,
    log_stderr: Path,
    stdin_data: str | None = None,
    job_id: str | None = None,
) -> int:
    env = dict(**os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # Avoid stale SSL_CERT_FILE from the host environment breaking httpx/OpenAI
    env.pop("SSL_CERT_FILE", None)
    env.pop("REQUESTS_CA_BUNDLE", None)
    timeout_seconds = _max_subprocess_timeout_seconds()
    with log_stdout.open("ab") as out, log_stderr.open("ab") as err:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE if stdin_data is not None else None,
            stdout=out,
            stderr=err,
        )
        if stdin_data is not None and proc.stdin:
            proc.stdin.write(stdin_data.encode("utf-8"))
            proc.stdin.close()
        try:
            return proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Hung subprocess â€” kill it so the job cannot stay stuck forever.
            proc.kill()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            message = (
                f"Subprocess exceeded {timeout_seconds}s timeout and was killed "
                f"(job_id={job_id or 'unknown'}): {' '.join(command)}"
            )
            app_logger.error(message)
            _write_to_stderr_log(log_stderr, f"âŒ {message}")
            return _TIMEOUT_EXIT_CODE


def _append_log(log_path: Path, message: str) -> None:
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[webhook] {message}\n")
    except Exception:
        return


def _notify_webhook(url: str, payload: dict) -> tuple[bool, str | None]:
    if not url:
        return False, "webhook url not set"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return True, None
    except (HTTPError, URLError, TimeoutError) as exc:
        # Do not fail the pipeline on webhook errors
        return False, str(exc)


def _notify_matching_complete(job: PipelineJob) -> tuple[bool, str | None]:
    payload = {
        "event": "matching_complete",
        "job_id": job.job_id,
        "session_id": job.session_id,
        "status": job.status,
        "stage": job.stage,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    url = N8N_PIPELINE_WEBHOOK_URL or N8N_MATCHING_WEBHOOK_URL
    return _notify_webhook(url, payload)


def _notify_final_complete(job: PipelineJob) -> tuple[bool, str | None]:
    payload = {
        "event": "final_complete",
        "job_id": job.job_id,
        "session_id": job.session_id,
        "status": job.status,
        "stage": job.stage,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    url = N8N_PIPELINE_WEBHOOK_URL or N8N_FINAL_WEBHOOK_URL
    return _notify_webhook(url, payload)


def _notify_format_complete(job: PipelineJob) -> tuple[bool, str | None]:
    payload = {
        "event": "format_complete",
        "job_id": job.job_id,
        "session_id": job.session_id,
        "status": job.status,
        "stage": job.stage,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    url = N8N_PIPELINE_WEBHOOK_URL or N8N_FINAL_WEBHOOK_URL
    return _notify_webhook(url, payload)


def _resolve_offer_experience_range(
    job: PipelineJob,
    offer_path: Path | None,
) -> tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """Return (min_years, max_years, display, experience_level) for folder overlap."""
    from service.offer_store import get_offer_by_id, fetch_experience_range, display_experience_range

    min_y: Optional[float] = None
    max_y: Optional[float] = None
    display: Optional[str] = None
    level: Optional[str] = None

    if job.offer_id:
        offer = get_offer_by_id(str(job.offer_id))
        if offer:
            level = offer.experience_level
            if offer.experience_range_id:
                er = fetch_experience_range(offer.experience_range_id)
                if er:
                    min_y = er.get("min_years")
                    max_y = er.get("max_years")
                    display = er.get("display")

    if min_y is None and max_y is None and offer_path and offer_path.exists():
        text = ""
        try:
            text = offer_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        if not text.strip() and OFFER_EXTRACTION_AVAILABLE:
            try:
                success, extracted, _method = extract_offer_text(offer_path)
                if success:
                    text = extracted
            except Exception:
                pass
        if text.strip():
            from service.offer_parser import _extract_experience_range

            min_y, max_y = _extract_experience_range(text)
            display = display_experience_range(min_y, max_y)

    return min_y, max_y, display, level


def _collect_mounted_cv_sources(
    profile: str,
    seniority_folders: list[str],
) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = []
    profile_normalized = normalize_profile(profile)
    for folder in seniority_folders:
        seniority_normalized = normalize_seniority(folder)
        cv_dir = CV_THEQUE_DIR / profile_normalized / seniority_normalized / "extracted"
        if cv_dir.exists() and any(cv_dir.glob("*.json")):
            sources.append((folder, cv_dir))
    return sources


def _merge_cv_pool(session_id: str, sources: list[tuple[str, Path]]) -> tuple[Path, int]:
    """Copy JSON CVs from one or more seniority folders into a single session pool."""
    pool_dir = CURRENT_DIR / "cv_pool" / session_id
    if pool_dir.exists():
        shutil.rmtree(pool_dir)
    pool_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    seen: set[str] = set()
    for folder, src_dir in sources:
        for cv_file in src_dir.glob("*.json"):
            if not cv_file.is_file():
                continue
            dest_name = cv_file.name
            if dest_name in seen:
                dest_name = f"{folder}_{dest_name}"
            shutil.copy2(cv_file, pool_dir / dest_name)
            seen.add(dest_name)
            count += 1
    return pool_dir, count


def _matching_experience_context_for_job(job: PipelineJob, offer_path: Path | None) -> str:
    _min, _max, display, level = _resolve_offer_experience_range(job, offer_path)
    return build_matching_experience_context(display, level)


def _load_cvs_from_library(job: PipelineJob, stdout_log: Path, stderr_log: Path) -> tuple[bool, str | None]:
    """Load CVs from CV_Theque for all seniority folders overlapping the offer experience range."""
    try:
        _write_to_stdout_log(stdout_log, f"[RUNNER] ===== Starting local CV library loading =====")
        _write_to_stdout_log(stdout_log, f"[RUNNER] Job ID: {job.job_id}")
        _write_to_stdout_log(stdout_log, f"[RUNNER] Session ID: {job.session_id}")
        
        profile = job.artifacts.detected_profile
        offer_path = Path(job.artifacts.input_offer_path or "")
        min_y, max_y, range_display, _exp_level = _resolve_offer_experience_range(
            job, offer_path if offer_path.exists() else None
        )
        seniority_folders = resolve_seniority_folders(min_y, max_y)

        _write_to_stdout_log(stdout_log, f"[RUNNER] Detected profile: {profile}")
        _write_to_stdout_log(
            stdout_log,
            f"[RUNNER] Experience range: min={min_y} max={max_y} display={range_display!r}",
        )
        _write_to_stdout_log(
            stdout_log,
            f"[RUNNER] Seniority folders (overlap): {', '.join(seniority_folders)}",
        )

        if not profile:
            message = "Profile not detected for CV library loading"
            _write_to_stderr_log(stderr_log, f"âŒ {message}")
            _write_to_stderr_log(stderr_log, "[RUNNER] Profile not detected")
            return False, message

        if not seniority_folders:
            message = "Aucun dossier sÃ©nioritÃ© applicable pour cette plage d'expÃ©rience."
            _write_to_stderr_log(stderr_log, f"âŒ {message}")
            return False, message

        _write_to_stdout_log(
            stdout_log,
            f"ðŸ”„ Loading CVs from CV_Theque: profile={profile}, folders={seniority_folders}",
        )

        # Resolve session_id early â€” needed for multi-folder cv_pool path.
        preset_session_id = (job.session_id or "").strip()
        if preset_session_id and preset_session_id != "pending":
            session_id = preset_session_id
            _write_to_stdout_log(stdout_log, f"[RUNNER] Reusing preset session_id: {session_id}")
        else:
            session_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            _write_to_stdout_log(stdout_log, f"[RUNNER] Creating session_id: {session_id}")

        mounted_sources = _collect_mounted_cv_sources(profile, seniority_folders)
        cv_count = 0
        used_direct_cv_bank = False
        final_cv_dir: Path | None = None

        if len(seniority_folders) == 1 and len(mounted_sources) == 1:
            _folder, cv_dir = mounted_sources[0]
            json_files = [p for p in cv_dir.glob("*.json") if p.is_file()]
            cv_count = len(json_files)
            if cv_count:
                used_direct_cv_bank = True
                final_cv_dir = cv_dir
                _write_to_stdout_log(
                    stdout_log,
                    f"[RUNNER] Direct CV_Theque read: {_folder} ({cv_count} JSON(s))",
                )
        elif mounted_sources:
            final_cv_dir, cv_count = _merge_cv_pool(session_id, mounted_sources)
            used_direct_cv_bank = True
            _write_to_stdout_log(
                stdout_log,
                f"[RUNNER] Merged {cv_count} CV JSON(s) from {len(mounted_sources)} folder(s) -> {final_cv_dir}",
            )

        if not used_direct_cv_bank:
            message = f"Aucun CV JSON trouve dans la CVtheque locale pour {profile} / {seniority_folders}."
            _write_to_stderr_log(stderr_log, message)
            return False, message

        if cv_count == 0 or final_cv_dir is None:
            message = "Aucun CV n'a pu Ãªtre chargÃ© depuis la CVtheque locale."
            _write_to_stderr_log(stderr_log, f"âŒ {message}")
            return False, message

        _write_to_stdout_log(stdout_log, f"âœ… Successfully resolved {cv_count} CVs from local CV library")
        _write_to_stdout_log(stdout_log, f"[RUNNER] Successfully resolved {cv_count} CVs from local CV library")

        if used_direct_cv_bank:
            job.artifacts.input_cv_dir = str(final_cv_dir)
            write_cv_source_marker(session_id, final_cv_dir)
            _write_to_stdout_log(stdout_log, f"[RUNNER] CV source marker written for session {session_id}")
        else:
            intermediary_dir = CURRENT_DIR / "intermediary_structured" / session_id
            intermediary_dir.mkdir(parents=True, exist_ok=True)
            for cv_file in final_cv_dir.glob("*.json"):
                shutil.move(str(cv_file), str(intermediary_dir / cv_file.name))
            shutil.rmtree(final_cv_dir, ignore_errors=True)
            job.artifacts.input_cv_dir = str(intermediary_dir)

        job.session_id = session_id
        if job.limit_count and cv_count > job.limit_count:
            job.cv_count = job.limit_count
            _write_to_stdout_log(
                stdout_log,
                f"[RUNNER] Matching limited to {job.limit_count} CV(s) (pool has {cv_count})",
            )
        else:
            job.cv_count = cv_count
        job.artifacts.matching_results_dir = str(CURRENT_DIR / "matching_results" / session_id)
        job.artifacts.final_results_dir = str(CURRENT_DIR / "final_result" / session_id)
        job.artifacts.formatted_cv_dir = str(CURRENT_DIR / "formatted_cv" / session_id)
        job.artifacts.archive_dir = str(ARCHIVE_DIR / session_id)
        update_job(job)
        _write_to_stdout_log(stdout_log, "[RUNNER] Updated job with session_id and paths")

        _write_to_stdout_log(stdout_log, f"âœ… Session created: {session_id} with {cv_count} CVs")
        _write_to_stdout_log(stdout_log, "[RUNNER] ===== local CV library loading completed successfully =====")

        return True, None

    except Exception as e:
        message = f"Unexpected error loading CV library: {type(e).__name__}: {e}"
        _write_to_stderr_log(stderr_log, f"âŒ {message}")
        _write_to_stderr_log(stderr_log, f"[RUNNER] CV library loading error: {type(e).__name__}: {e}")
        return False, message


def _external_cv_dir(job: PipelineJob) -> str | None:
    """Return the CV source path when it points outside intermediary_structured (Action 230)."""
    cv_dir = (job.artifacts.input_cv_dir or "").strip()
    if not cv_dir:
        return None
    intermediary_root = str(CURRENT_DIR / "intermediary_structured").replace("\\", "/")
    if cv_dir.replace("\\", "/").startswith(intermediary_root):
        return None
    return cv_dir


def _parse_offer_and_detect_profile(job: PipelineJob, offer_path: Path, stdout_log: Path, stderr_log: Path) -> bool:
    """Parse offer file and detect profile/seniority using LLM with SFTP discovery."""
    try:
        _write_to_stdout_log(stdout_log, "ðŸ” Parsing offer to detect profile and seniority...")
        
        offer_parser = get_offer_parser(stdout_log=stdout_log, stderr_log=stderr_log)
        
        # Use new LLM+SFTP method with caching and optimization
        profile, seniority = offer_parser.parse_offer(offer_path, use_llm=True)
        
        _write_to_stdout_log(stdout_log, f"âœ… Detected profile: {profile}, seniority: {seniority}")
        
        # Update job with detected values
        job.artifacts.detected_profile = profile
        job.artifacts.detected_seniority = seniority
        update_job(job)
        
        return True
    
    except Exception as e:
        _write_to_stderr_log(stderr_log, f"âŒ Offer parsing failed: {str(e)}")
        return False


def _run_transform_and_ingest(job: PipelineJob, stdout_log: Path, stderr_log: Path) -> None:
    if not ENABLE_PG_INGEST:
        return

    session_id = job.session_id
    archive_dir = Path(job.artifacts.archive_dir or (ARCHIVE_DIR / session_id))
    if not archive_dir.exists():
        job.transform_exit_code = 1
        job.status = "failed"
        job.stage = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = "Archive directory not found for transform"
        update_job(job)
        return

    output_path = PROJECT_ROOT / "AI_Assistance" / "transformed_sessions" / f"transformed_session_{session_id}.json"
    transform_cmd = [
        "python",
        "-X",
        "utf8",
        str(TRANSFORMER_SCRIPT),
        "--session-dir",
        str(archive_dir),
        "--output",
        str(output_path),
    ]

    job.stage = "running_transformer"
    update_job(job)
    job.transform_exit_code = _run_subprocess(
        command=transform_cmd,
        cwd=PROJECT_ROOT,
        log_stdout=stdout_log,
        log_stderr=stderr_log,
    )
    if job.transform_exit_code != 0:
        job.status = "failed"
        job.stage = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = f"Transformer failed with exit code {job.transform_exit_code}"
        update_job(job)
        return

    job.artifacts.transformed_json_path = str(output_path)
    update_job(job)

    ingest_cmd = [
        "python",
        "-X",
        "utf8",
        str(INGEST_SCRIPT),
        "--input",
        str(output_path),
        "--session-id",
        session_id,
    ]
    if PIPELINE_PG_DSN:
        ingest_cmd.extend(["--dsn", PIPELINE_PG_DSN])

    job.stage = "running_ingestor"
    update_job(job)
    job.ingest_exit_code = _run_subprocess(
        command=ingest_cmd,
        cwd=PROJECT_ROOT,
        log_stdout=stdout_log,
        log_stderr=stderr_log,
    )
    if job.ingest_exit_code != 0:
        job.status = "failed"
        job.stage = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = f"Ingest failed with exit code {job.ingest_exit_code}"
        update_job(job)
        return


def run_pipeline_job(job_id: str) -> None:
    """Outer guard: any unhandled exception marks the job failed so it can never
    stay stuck in 'running' forever (C-3)."""
    try:
        _run_pipeline_job_impl(job_id)
    except Exception as e:
        app_logger.error(
            f"Unhandled exception in pipeline job {job_id}: {e}\n{traceback.format_exc()}"
        )
        job = get_job(job_id)
        if job:
            job.status = "failed"
            job.stage = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = f"Erreur interne: {str(e)}"
            update_job(job)


def _run_pipeline_job_impl(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return

    job.status = "running"
    job.stage = "running_pipeline"
    job.started_at = datetime.utcnow()
    update_job(job)

    job_dir = API_JOBS_DIR / job_id
    logs_dir = job_dir / "logs"
    stdout_log = logs_dir / "pipeline_stdout.log"
    stderr_log = logs_dir / "pipeline_stderr.log"

    offer_path = Path(job.artifacts.input_offer_path or "")
    cv_dir = Path(job.artifacts.input_cv_dir or "")
    is_reuse_mode = job.artifacts.reuse_session_id is not None
    is_offer_only_mode = job.input_mode == "offer_only"

    # Copy offer to {DATA_ROOT}/current/offer/{session_id}/ for standard/reuse modes.
    # Action 230: skip for offer_only â€” the recruiter upload already placed the
    # file under offer/{session_id}/ with its original filename.
    if not is_offer_only_mode and job.session_id and job.session_id != "pending":
        offer_dest_dir = CURRENT_DIR / "offer" / job.session_id
        offer_dest_dir.mkdir(parents=True, exist_ok=True)
        offer_dest = offer_dest_dir / offer_path.name
        if offer_path.exists():
            shutil.copy2(offer_path, offer_dest)

    if is_offer_only_mode:
        # OFFER ONLY MODE: Parse offer, load CVs from local CV library, skip extraction
        _append_log(stdout_log, "ðŸ”„ OFFER ONLY MODE - Parsing offer and loading CVs from local CV library")
        
        # Step 1: Parse offer to detect profile and seniority
        if not _parse_offer_and_detect_profile(job, offer_path, stdout_log, stderr_log):
            job.status = "failed"
            job.stage = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = "Unable to analyze the offer and detect the profile or seniority."
            update_job(job)
            return
        
        # Step 2: Load CVs from local CV library (this will create session_id)
        sftp_success, sftp_error = _load_cvs_from_library(job, stdout_log, stderr_log)
        if not sftp_success:
            job.status = "failed"
            job.stage = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = sftp_error or "Le chargement des CVs depuis la CVtheque locale a Ã©chouÃ©."
            update_job(job)
            return
        
        # Action 230: the offer file already lives on the data root from recruiter
        # upload. Only convert non-.txt uploads to .txt when the session folder
        # has no .txt yet â€” never write a duplicate generic offer.txt.
        offer_dest_dir = CURRENT_DIR / "offer" / job.session_id
        existing_txt = (
            sorted(offer_dest_dir.glob("*.txt"))
            if offer_dest_dir.exists()
            else []
        )
        if existing_txt:
            _append_log(stdout_log, f"âœ… Offer .txt already on session: {existing_txt[0].name}")
        elif offer_path.exists() and OFFER_EXTRACTION_AVAILABLE:
            offer_extension = offer_path.suffix.lower()
            if offer_extension != ".txt":
                _append_log(stdout_log, f"ðŸ”„ Converting offer from {offer_extension} to .txt format...")
                try:
                    success, offer_text, method = extract_offer_text(offer_path)
                    if success:
                        saved_path = save_offer_to_session(offer_text, job.session_id, offer_path.name)
                        _append_log(stdout_log, f"âœ… Offer extracted successfully using {method} method")
                        _append_log(stdout_log, f"   ðŸ“ Extracted {len(offer_text):,} characters")
                        _append_log(stdout_log, f"   ðŸ’¾ Saved to: {safe_relpath(saved_path)}")
                    else:
                        _append_log(stderr_log, f"âŒ Failed to extract offer: {offer_text}")
                except Exception as e:
                    _append_log(stderr_log, f"âŒ Error during offer extraction: {str(e)}")
            else:
                offer_dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(offer_path, offer_dest_dir / offer_path.name)
                _append_log(stdout_log, f"âœ… Offer copied as .txt: {offer_path.name}")

        job.pipeline_exit_code = 0  # No extraction needed
    
    elif is_reuse_mode:
        # REUSE MODE: Skip extraction, use existing CVs
        _append_log(stdout_log, f"ðŸ”„ REUSE MODE - Using existing CVs from session: {job.artifacts.reuse_session_id}")
        job.pipeline_exit_code = 0  # No extraction needed
    else:
        # STANDARD MODE: Extract CVs from uploaded files
        extraction_cmd = [
            "python",
            "-X",
            "utf8",
            str(PROJECT_ROOT / "script" / "01_extraction_and_validation.py"),
            "--session",
            job.session_id,
            "--input",
            str(cv_dir),
            "--offer",
            str(offer_dest),
        ]
        job.pipeline_exit_code = _run_subprocess(
            command=extraction_cmd,
            cwd=PROJECT_ROOT,
            log_stdout=stdout_log,
            log_stderr=stderr_log,
            job_id=job_id,
        )

        if job.pipeline_exit_code != 0:
            job.status = "failed"
            job.stage = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = f"Extraction failed with exit code {job.pipeline_exit_code}"
            update_job(job)
            return

    # Run matching (works for all modes: standard, reuse, offer_only)
    matcher_cmd = [
        "python",
        "-X",
        "utf8",
        str(PROJECT_ROOT / "script" / "matcher.py"),
        job.session_id,
    ]
    
    # For reuse mode, add the --reuse-session parameter
    if is_reuse_mode:
        matcher_cmd.extend(["--reuse-session", job.artifacts.reuse_session_id])

    external_cv = _external_cv_dir(job)
    if external_cv:
        matcher_cmd.extend(["--cv-dir", external_cv])

    exp_context = _matching_experience_context_for_job(job, offer_path if offer_path.exists() else None)
    if exp_context:
        matcher_cmd.extend(["--experience-context", exp_context])

    if job.limit_count:
        matcher_cmd.extend(["--limit", str(job.limit_count)])
    
    matcher_exit = _run_subprocess(
        command=matcher_cmd,
        cwd=PROJECT_ROOT,
        log_stdout=stdout_log,
        log_stderr=stderr_log,
        job_id=job_id,
    )
    if matcher_exit != 0:
        job.pipeline_exit_code = matcher_exit
        job.status = "failed"
        job.stage = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = f"Matcher failed with exit code {matcher_exit}"
        update_job(job)
        return

    job.status = "succeeded"
    job.stage = "matching_complete"
    job.completed_at = datetime.utcnow()
    job.matching_completed_at = job.completed_at
    update_job(job)
    # Fix 4 (Action 220): matching complete â†’ offer status_id = 4 (matched) + audit.
    if job.offer_id:
        try:
            from service.offer_store import set_offer_status_id as _set_status
            _set_status(str(job.offer_id), 4)
        except Exception as exc:
            _append_log(stdout_log, f"could not set offer {job.offer_id} status to matched: {exc}")
    try:
        from service.audit_store import audit_store as _audit
        _audit.log_event(
            event_type="pipeline_completed",
            description=f"Pipeline terminÃ© â€” {job.cv_count or 0} CVs matchÃ©s",
            actor_id=str(job.created_by) if job.created_by else None,
            target_id=job.job_id,
            target_type="job",
            metadata={"offer_id": str(job.offer_id) if job.offer_id else None,
                      "cv_count": job.cv_count or 0},
        )
    except Exception:
        pass
    if job.offer_id:
        try:
            from service.candidate_store import sync_appearances_from_matching as _sync_match
            matching_dir = CURRENT_DIR / "matching_results" / job.session_id
            _sync_match(job.session_id, str(job.offer_id), job.job_id, matching_dir)
            _append_log(stdout_log, "candidate appearances synced from matching results")
        except Exception as exc:
            _append_log(stdout_log, f"candidate appearance sync failed (non-blocking): {exc}")

    notified, error = _notify_matching_complete(job)
    if notified:
        _append_log(stdout_log, f"matching_complete webhook sent to {N8N_PIPELINE_WEBHOOK_URL or N8N_MATCHING_WEBHOOK_URL}")
    else:
        _append_log(stdout_log, f"matching_complete webhook failed: {error}")


def _advance_offer_status(job, status_id: int, event_type: str, description: str, log_path) -> None:
    """Fix 4 (Action 220): move the linked offer to a new status_id and audit it.

    Best-effort â€” never raises. Only acts when the job is linked to an offer.
    """
    if not getattr(job, "offer_id", None):
        return
    try:
        from service.offer_store import set_offer_status_id as _set_status
        _set_status(str(job.offer_id), status_id)
    except Exception as exc:
        _append_log(log_path, f"could not set offer {job.offer_id} status_id={status_id}: {exc}")
    try:
        from service.audit_store import audit_store as _audit
        _audit.log_event(
            event_type=event_type,
            description=description,
            actor_id=str(job.created_by) if job.created_by else None,
            target_id=str(job.offer_id),
            target_type="offer",
            metadata={"job_id": job.job_id, "session_id": job.session_id},
        )
    except Exception:
        pass


def start_job_thread(job_id: str) -> None:
    thread = threading.Thread(target=run_pipeline_job, args=(job_id,), daemon=True)
    thread.start()


_TEST_SCORE_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm", ".txt"}


def _resolve_tests_file_path(job, job_dir: Path) -> Optional[Path]:
    """Locate CoderPad / test-scores file for final scoring.

    Priority: persisted artifact path â†’ job inputs/ â†’ session tests/ archive.
    """
    ordered: list[Path] = []
    if job.artifacts.tests_file_path:
        ordered.append(Path(job.artifacts.tests_file_path))

    inputs_dir = job_dir / "inputs"
    if inputs_dir.is_dir():
        input_files = [
            f for f in inputs_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _TEST_SCORE_EXTENSIONS
        ]
        ordered.extend(sorted(input_files, key=lambda p: p.stat().st_mtime, reverse=True))

    if job.session_id:
        session_tests = CURRENT_DIR / "tests" / job.session_id
        if session_tests.is_dir():
            archived = [
                f for f in session_tests.iterdir()
                if f.is_file() and f.suffix.lower() in _TEST_SCORE_EXTENSIONS
            ]
            ordered.extend(sorted(archived, key=lambda p: p.stat().st_mtime, reverse=True))

    seen: set[str] = set()
    for path in ordered:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return path
    return None


def run_final_phase(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job.status = "running"
    job.stage = "running_final"
    update_job(job)

    job_dir = API_JOBS_DIR / job_id
    logs_dir = job_dir / "logs"
    stdout_log = logs_dir / "pipeline_stdout.log"
    stderr_log = logs_dir / "pipeline_stderr.log"

    final_cmd = [
        "python",
        "-X",
        "utf8",
        str(PROJECT_ROOT / "script" / "final_result.py"),
        "--session",
        job.session_id,
    ]
    # Re-fetch so tests_file_path from a just-uploaded CSV is visible (relaunch flow).
    job = get_job(job_id) or job
    tests_path = _resolve_tests_file_path(job, job_dir)
    if tests_path:
        final_cmd.extend(["--tests", str(tests_path)])
        _append_log(stdout_log, f"Test scores file: {safe_relpath(tests_path)}")
    else:
        final_cmd.append("--no-tests")
        _append_log(stdout_log, "No test scores file found â€” CV-only final scoring")
    external_cv = _external_cv_dir(job)
    if external_cv:
        final_cmd.extend(["--cv-dir", external_cv])
    selection_file = job_dir / "final_selection.json"
    if selection_file.exists():
        final_cmd.extend(["--candidates-file", str(selection_file)])
    final_exit = _run_subprocess(
        command=final_cmd,
        cwd=PROJECT_ROOT,
        log_stdout=stdout_log,
        log_stderr=stderr_log,
    )
    if final_exit != 0:
        job.pipeline_exit_code = final_exit
        job.status = "failed"
        job.stage = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = f"Final result failed with exit code {final_exit}"
        update_job(job)
        return

    _run_transform_and_ingest(job, stdout_log, stderr_log)
    if job.status == "failed":
        return

    job.status = "succeeded"
    job.stage = "final_complete"
    job.completed_at = datetime.utcnow()
    job.final_completed_at = job.completed_at
    update_job(job)
    if job.offer_id:
        try:
            from service.candidate_store import (
                sync_final_scores_from_result as _sync_final,
                _resolve_final_path,
            )
            final_path = _resolve_final_path(job.session_id)
            if final_path:
                _sync_final(job.session_id, str(job.offer_id), final_path)
                _append_log(stdout_log, "candidate final scores synced")
        except Exception as exc:
            _append_log(stdout_log, f"candidate final score sync failed (non-blocking): {exc}")
    # Fix 4: final result generated â†’ offer status_id = 5 (final_result)
    _advance_offer_status(job, 5, "offer_final_result",
                          "RÃ©sultat final gÃ©nÃ©rÃ©", stdout_log)
    notified, error = _notify_final_complete(job)
    if notified:
        _append_log(stdout_log, f"final_complete webhook sent to {N8N_PIPELINE_WEBHOOK_URL or N8N_FINAL_WEBHOOK_URL}")
    else:
        _append_log(stdout_log, f"final_complete webhook failed: {error}")


def run_format_phase(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job.status = "running"
    job.stage = "running_format"
    update_job(job)

    job_dir = API_JOBS_DIR / job_id
    logs_dir = job_dir / "logs"
    stdout_log = logs_dir / "pipeline_stdout.log"
    stderr_log = logs_dir / "pipeline_stderr.log"

    # Ensure final_result exists (archiver may have moved it)
    final_dir = CURRENT_DIR / "final_result" / job.session_id
    final_path = final_dir / "final_result.json"
    if not final_path.exists():
        archive_fallback = ARCHIVE_DIR / job.session_id / "final" / "final_result.json"
        if archive_fallback.exists():
            final_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive_fallback, final_path)
        else:
            # If final_result doesn't exist, try to create it from matching results
            # This allows formatting without final scoring
            matching_dir = CURRENT_DIR / "matching_results" / job.session_id
            if matching_dir.exists():
                matching_files = list(matching_dir.glob("*.json"))
                if matching_files:
                    import json
                    matching_file = matching_files[0]
                    with open(matching_file, 'r') as f:
                        matching_data = json.load(f)
                    
                    # Create final_result.json from matching results
                    final_dir.mkdir(parents=True, exist_ok=True)
                    final_candidates = []
                    for candidate in matching_data.get('candidates', []):
                        # Map matching result structure to final result structure
                        final_candidate = {
                            'name': candidate.get('candidate_name'),  # CV generator expects 'name' field
                            'candidate_name': candidate.get('candidate_name'),
                            'cv_filename': candidate.get('cv_filename'),
                            'overall_score': candidate.get('overall_score', 0),
                            'final_score': candidate.get('overall_score', 0),  # Use overall as final if no final scoring
                            'test_score': None,  # No test score if final scoring was skipped
                            'rank': None  # No rank if final scoring was skipped
                        }
                        final_candidates.append(final_candidate)
                    
                    final_result = {
                        'session_id': job.session_id,
                        'job_title': matching_data.get('job_title', ''),
                        'timestamp': matching_data.get('timestamp', ''),
                        'candidates': final_candidates
                    }
                    
                    with open(final_path, 'w') as f:
                        json.dump(final_result, f, indent=2)
                    
                    _append_log(stdout_log, f"Created final_result.json from matching results for formatting without final scoring")

    # Clear stale formatted output so a re-format (e.g. a new template or a smaller
    # selection) cannot leave behind files from a previous run, and drop the cached
    # download zip so the next download reflects the new output (Action 226 Fix 2A).
    formatted_dir = CURRENT_DIR / "formatted_cv" / job.session_id
    archive_formatted_dir = ARCHIVE_DIR / job.session_id / "cvs" / "formatted"
    for stale_dir in (formatted_dir, archive_formatted_dir):
        if stale_dir.exists():
            try:
                shutil.rmtree(stale_dir)
            except Exception as exc:
                _append_log(stderr_log, f"[WARNING] could not clear {stale_dir}: {exc}")
    for stale_zip in job_dir.glob(f"Formatted_CVs_{job.session_id}.zip"):
        try:
            stale_zip.unlink()
        except Exception as exc:
            _append_log(stderr_log, f"[WARNING] could not remove cached zip {stale_zip}: {exc}")

    cv_cmd = [
        "python",
        "-X",
        "utf8",
        str(PROJECT_ROOT / "script" / "cv_generator.py"),
        "--session",
        job.session_id,
        "--non-interactive",
        "--skip-threshold-check",
    ]
    template_name = job.template_name or "classic"
    cv_cmd.extend(["--template", template_name])
    # Manual candidate selection (Action 226 Fix 2C) takes precedence over a count.
    selection_file = job_dir / "format_selection.json"
    if selection_file.exists():
        cv_cmd.extend(["--candidates-file", str(selection_file)])
    elif job.limit_count:
        cv_cmd.extend(["--limit", str(job.limit_count)])
    cv_exit = _run_subprocess(
        command=cv_cmd,
        cwd=PROJECT_ROOT,
        log_stdout=stdout_log,
        log_stderr=stderr_log,
        stdin_data=None,
    )
    if cv_exit != 0:
        job.pipeline_exit_code = cv_exit
        job.status = "failed"
        job.stage = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = f"CV generator failed with exit code {cv_exit}"
        update_job(job)
        return

    # Action 234: automatic archiving removed â€” files stay in current/ until the
    # recruiter explicitly archives the offer (PATCH â€¦/status archived â†’ archive_session_data).
    _append_log(stdout_log, "â„¹ï¸  Archivage automatique dÃ©sactivÃ© â€” les fichiers restent dans current/")

    job.status = "succeeded"
    job.stage = "format_complete"
    job.completed_at = datetime.utcnow()
    job.format_completed_at = job.completed_at
    update_job(job)
    # Fix 4: CVs formatted â†’ offer status_id = 6 (formatted)
    _advance_offer_status(job, 6, "offer_formatted",
                          "CVs formatÃ©s", stdout_log)
    notified, error = _notify_format_complete(job)
    if notified:
        _append_log(stdout_log, f"format_complete webhook sent to {N8N_PIPELINE_WEBHOOK_URL or N8N_FINAL_WEBHOOK_URL}")
    else:
        _append_log(stdout_log, f"format_complete webhook failed: {error}")


def start_phase_thread(job_id: str, phase: str) -> None:
    if phase == "final":
        thread = threading.Thread(target=run_final_phase, args=(job_id,), daemon=True)
    elif phase == "format":
        thread = threading.Thread(target=run_format_phase, args=(job_id,), daemon=True)
    else:
        thread = threading.Thread(target=run_pipeline_job, args=(job_id,), daemon=True)
    thread.start()




