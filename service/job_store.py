"""
service/job_store.py

PostgreSQL-backed store for the jobs.pipeline_jobs table.
Schema lives in service/migrations/003_jobs_schema.sql.

Connection is read from DATABASE_URL (same as service/user_store.py and
service/offer_store.py). Public method signatures are unchanged from the
former SQLite implementation so service/api.py and service/runner.py need
no changes.
"""
from __future__ import annotations

import json
import os

import psycopg2
import psycopg2.extras

from service.models import PipelineArtifacts, PipelineJob

ACTIVE_JOB_STATUSES = ("queued", "pending", "running", "processing")

psycopg2.extras.register_uuid()  # map UUID columns (offer_id, created_by) ↔ uuid.UUID


def _connect() -> psycopg2.extensions.connection:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL env var is not set. "
            "Add it to config/.env (e.g. postgresql://postgres:postgres@localhost:5432/cv_pipeline)"
        )
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


# Idempotent schema bootstrap — mirrors migration 003_jobs_schema.sql so the
# table self-heals on startup even if the migration was not run manually.
_INIT_SQL = """
CREATE SCHEMA IF NOT EXISTS jobs;

CREATE TABLE IF NOT EXISTS jobs.pipeline_jobs (
  id              VARCHAR(36) PRIMARY KEY,
  session_id      VARCHAR(50),
  status          VARCHAR(20) NOT NULL DEFAULT 'pending',
  stage           VARCHAR(50),
  input_mode      VARCHAR(20),
  offer_filename  VARCHAR(255),
  offer_id        UUID REFERENCES offers.job_offers(id) ON DELETE SET NULL,
  created_by      UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  cv_count        INTEGER DEFAULT 0,
  error_message   TEXT,
  archive_enabled     BOOLEAN DEFAULT true,
  format_cvs          BOOLEAN DEFAULT false,
  template_name       VARCHAR(50),
  limit_count         INTEGER,
  pipeline_exit_code  INTEGER,
  transform_exit_code INTEGER,
  ingest_exit_code    INTEGER,
  artifacts           JSONB NOT NULL DEFAULT '{}',
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_session_id ON jobs.pipeline_jobs(session_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_status     ON jobs.pipeline_jobs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_created_by ON jobs.pipeline_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_offer_id   ON jobs.pipeline_jobs(offer_id);
"""


def init_db() -> None:
    """
    Create the jobs schema/table/indexes if they don't exist (idempotent).

    In production the objects are created by migration 003 run as the `postgres`
    superuser, because the runtime role (api_user) has no CREATE privilege on the
    database. We still attempt the DDL here for convenience (e.g. local dev as a
    privileged role) but tolerate InsufficientPrivilege so startup never fails.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_INIT_SQL)
            conn.commit()
    except psycopg2.errors.InsufficientPrivilege:
        conn.rollback()
        # Schema is managed by migration 003 (postgres) — nothing to do here.
    finally:
        conn.close()


def _row_to_job(row: dict) -> PipelineJob:
    artifacts_raw = row.get("artifacts") or {}
    if isinstance(artifacts_raw, str):
        artifacts_raw = json.loads(artifacts_raw or "{}")
    return PipelineJob(
        job_id=row["id"],
        session_id=row["session_id"],
        status=row["status"],
        stage=row["stage"],
        created_at=row["created_at"],
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        matching_completed_at=row.get("matching_completed_at"),
        final_completed_at=row.get("final_completed_at"),
        format_completed_at=row.get("format_completed_at"),
        input_mode=row.get("input_mode") or "cv_folder_offer",
        offer_filename=row.get("offer_filename"),
        cv_count=row.get("cv_count") or 0,
        archive_enabled=bool(row["archive_enabled"]) if row.get("archive_enabled") is not None else True,
        format_cvs=bool(row["format_cvs"]) if row.get("format_cvs") is not None else False,
        template_name=row.get("template_name"),
        limit_count=row.get("limit_count"),
        pipeline_exit_code=row.get("pipeline_exit_code"),
        transform_exit_code=row.get("transform_exit_code"),
        ingest_exit_code=row.get("ingest_exit_code"),
        error_message=row.get("error_message"),
        offer_id=str(row["offer_id"]) if row.get("offer_id") else None,
        created_by=str(row["created_by"]) if row.get("created_by") else None,
        updated_at=row.get("updated_at"),
        artifacts=PipelineArtifacts.parse_obj(artifacts_raw),
    )


def create_job(job: PipelineJob) -> None:
    sql = """
        INSERT INTO jobs.pipeline_jobs (
            id, session_id, status, stage, created_at, started_at, completed_at,
            input_mode, offer_filename, offer_id, created_by, cv_count,
            archive_enabled, format_cvs, template_name, limit_count,
            pipeline_exit_code, transform_exit_code, ingest_exit_code,
            error_message, artifacts, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s::jsonb, NOW()
        )
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                job.job_id,
                job.session_id,
                job.status,
                job.stage,
                job.created_at,
                job.started_at,
                job.completed_at,
                job.input_mode,
                job.offer_filename,
                job.offer_id,
                job.created_by,
                job.cv_count,
                job.archive_enabled,
                job.format_cvs,
                job.template_name,
                job.limit_count,
                job.pipeline_exit_code,
                job.transform_exit_code,
                job.ingest_exit_code,
                job.error_message,
                job.artifacts.json(),
            ))
            conn.commit()


def get_active_job_for_offer(offer_id: str) -> PipelineJob | None:
    sql = """
        SELECT * FROM jobs.pipeline_jobs
        WHERE offer_id = %s
          AND status = ANY(%s)
        ORDER BY created_at ASC
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(offer_id), list(ACTIVE_JOB_STATUSES)))
            row = cur.fetchone()
            return _row_to_job(dict(row)) if row else None


def create_job_unless_active(job: PipelineJob) -> tuple[bool, PipelineJob]:
    """Insert a job unless the linked offer already has an active job."""
    if not job.offer_id:
        create_job(job)
        return True, job

    sql = """
        INSERT INTO jobs.pipeline_jobs (
            id, session_id, status, stage, created_at, started_at, completed_at,
            input_mode, offer_filename, offer_id, created_by, cv_count,
            archive_enabled, format_cvs, template_name, limit_count,
            pipeline_exit_code, transform_exit_code, ingest_exit_code,
            error_message, artifacts, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s::jsonb, NOW()
        )
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM jobs.pipeline_jobs
                WHERE offer_id = %s AND status = ANY(%s)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (str(job.offer_id), list(ACTIVE_JOB_STATUSES)),
            )
            existing = cur.fetchone()
            if existing:
                conn.rollback()
                return False, _row_to_job(dict(existing))
            try:
                cur.execute(sql, (
                    job.job_id,
                    job.session_id,
                    job.status,
                    job.stage,
                    job.created_at,
                    job.started_at,
                    job.completed_at,
                    job.input_mode,
                    job.offer_filename,
                    job.offer_id,
                    job.created_by,
                    job.cv_count,
                    job.archive_enabled,
                    job.format_cvs,
                    job.template_name,
                    job.limit_count,
                    job.pipeline_exit_code,
                    job.transform_exit_code,
                    job.ingest_exit_code,
                    job.error_message,
                    job.artifacts.json(),
                ))
                conn.commit()
                return True, job
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                existing_job = get_active_job_for_offer(str(job.offer_id))
                if existing_job:
                    return False, existing_job
                raise


def update_job(job: PipelineJob) -> None:
    sql = """
        UPDATE jobs.pipeline_jobs SET
            session_id = %s,
            status = %s,
            stage = %s,
            started_at = %s,
            completed_at = %s,
            matching_completed_at = %s,
            final_completed_at = %s,
            format_completed_at = %s,
            input_mode = %s,
            offer_filename = %s,
            offer_id = %s,
            created_by = %s,
            cv_count = %s,
            archive_enabled = %s,
            format_cvs = %s,
            template_name = %s,
            limit_count = %s,
            pipeline_exit_code = %s,
            transform_exit_code = %s,
            ingest_exit_code = %s,
            error_message = %s,
            artifacts = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                job.session_id,
                job.status,
                job.stage,
                job.started_at,
                job.completed_at,
                job.matching_completed_at,
                job.final_completed_at,
                job.format_completed_at,
                job.input_mode,
                job.offer_filename,
                job.offer_id,
                job.created_by,
                job.cv_count,
                job.archive_enabled,
                job.format_cvs,
                job.template_name,
                job.limit_count,
                job.pipeline_exit_code,
                job.transform_exit_code,
                job.ingest_exit_code,
                job.error_message,
                job.artifacts.json(),
                job.job_id,
            ))
            conn.commit()


def get_job(job_id: str) -> PipelineJob | None:
    sql = "SELECT * FROM jobs.pipeline_jobs WHERE id = %s LIMIT 1"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (job_id,))
            row = cur.fetchone()
            return _row_to_job(dict(row)) if row else None


def get_jobs_by_status(status: str) -> list[PipelineJob]:
    """Return all jobs currently in the given status (e.g. 'running')."""
    sql = "SELECT * FROM jobs.pipeline_jobs WHERE status = %s"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status,))
            return [_row_to_job(dict(r)) for r in cur.fetchall()]


def get_job_by_session_id(session_id: str) -> PipelineJob | None:
    """Return the most recent job with the given session_id (excludes 'pending')."""
    sql = """
        SELECT * FROM jobs.pipeline_jobs
        WHERE session_id = %s AND session_id != 'pending'
        ORDER BY created_at DESC
        LIMIT 1
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (session_id,))
            row = cur.fetchone()
            return _row_to_job(dict(row)) if row else None


def get_job_status_counts() -> dict:
    """System-wide pipeline-job counts for the admin stats endpoint.

    Returns {total, completed, failed, running} (Workstream 3).
    """
    sql = "SELECT status, COUNT(*) AS cnt FROM jobs.pipeline_jobs GROUP BY status"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            by_status = {r["status"]: r["cnt"] for r in cur.fetchall()}
    return {
        "total": sum(by_status.values()),
        "completed": by_status.get("completed", 0),
        "failed": by_status.get("failed", 0),
        "running": by_status.get("running", 0),
    }


def get_recent_job_events(limit: int = 20) -> list:
    """System-wide recent pipeline completions and failures for the admin activity feed.

    Each row: {status, offer_title, user_name, ts}.
    """
    sql = """
        SELECT j.status,
               o.title AS offer_title,
               u.full_name AS user_name,
               COALESCE(j.completed_at, j.updated_at, j.created_at) AS ts
        FROM jobs.pipeline_jobs j
        LEFT JOIN offers.job_offers o ON o.id = j.offer_id
        LEFT JOIN auth.users u ON u.id = j.created_by
        WHERE j.status IN ('completed', 'failed')
        ORDER BY ts DESC
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return [dict(r) for r in cur.fetchall()]


def fail_stale_jobs(max_minutes: int) -> list[str]:
    """
    Mark every 'running' job whose updated_at is older than max_minutes as failed
    (stale-job sweeper, C-7). Returns the list of affected job ids for logging.
    """
    sql = """
        UPDATE jobs.pipeline_jobs
        SET status = 'failed',
            stage = 'failed',
            error_message = 'Job expiré — timeout dépassé',
            completed_at = NOW(),
            updated_at = NOW()
        WHERE status = 'running'
          AND updated_at < NOW() - (%s || ' minutes')::interval
        RETURNING id
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(max_minutes),))
            rows = cur.fetchall()
            conn.commit()
            return [r["id"] for r in rows]
