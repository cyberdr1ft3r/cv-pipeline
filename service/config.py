from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MAIN_SCRIPT = PROJECT_ROOT / "script" / "main.py"
TRANSFORMER_SCRIPT = PROJECT_ROOT / "AI_Assistance" / "script" / "transformer.py"
INGEST_SCRIPT = PROJECT_ROOT / "AI_Assistance" / "script" / "ingest_session_pg.py"


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# Load env values from common local files if present (without overriding real env)
_load_env_file(PROJECT_ROOT / ".env")
_load_env_file(PROJECT_ROOT / "automation" / ".env.automation")
_load_env_file(PROJECT_ROOT / "config" / ".env")
_load_env_file(PROJECT_ROOT / "service" / ".env")


# ── DATA ROOT (single source of truth — Action 227) ───────────────────────────
# All pipeline storage resolves under DATA_ROOT. In production DATA_ROOT points
# at the mounted SFTP share (/sftp/cv_tech/files/Data); for local dev it falls
# back to <project>/data. The resolver lives in script.storage_paths so the
# service and the pipeline subprocesses share exactly one definition. It is
# imported *after* the .env files above so a DATA_ROOT defined there is honoured.
from script.storage_paths import (  # noqa: E402
    DATA_ROOT,
    CURRENT_DIR,
    ARCHIVE_DIR,
    API_JOBS_DIR,
    CV_THEQUE_DIR,
    current_dir,
    session_dir,
    archive_session_dir,
    safe_relpath,
    write_cv_source_marker,
    read_cv_source_marker,
    resolve_session_cv_dir,
    cleanup_session_data,
    archive_session_data,
)

# Backwards-compatible alias (legacy imports expect DATA_DIR).
DATA_DIR = DATA_ROOT


PIPELINE_PG_DSN = os.getenv("PIPELINE_PG_DSN", "").strip()
ENABLE_PG_INGEST = os.getenv("ENABLE_PG_INGEST", "false").strip().lower() in {"1", "true", "yes"}
N8N_MATCHING_WEBHOOK_URL = os.getenv("N8N_MATCHING_WEBHOOK_URL", "").strip()
N8N_FINAL_WEBHOOK_URL = os.getenv("N8N_FINAL_WEBHOOK_URL", "").strip()
N8N_PIPELINE_WEBHOOK_URL = os.getenv("N8N_PIPELINE_WEBHOOK_URL", "").strip()

# Ensure the job-metadata directory exists (Action 227: create api_jobs/ on the
# SFTP mount if missing). Best-effort: never crash import if the mount is absent.
try:
    API_JOBS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
