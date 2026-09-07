-- Migration 003: pipeline jobs schema (migrated from SQLite data/api_jobs/jobs.db).
-- Run after 001_auth_offers_schema.sql and 002_offer_columns.sql. Idempotent.
--
-- NOTE: this is a SUPERSET of the originally proposed schema. The extra columns
-- (artifacts, archive_enabled, format_cvs, template_name, limit_count,
--  pipeline_exit_code, transform_exit_code, ingest_exit_code) are required because
-- service/runner.py and service/api.py round-trip these fields of the PipelineJob /
-- PipelineArtifacts model. Dropping them would break the pipeline.

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
  -- Extra columns required by the existing PipelineJob / PipelineArtifacts model
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

CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_session_id
  ON jobs.pipeline_jobs(session_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_status
  ON jobs.pipeline_jobs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_created_by
  ON jobs.pipeline_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_offer_id
  ON jobs.pipeline_jobs(offer_id);

-- Runtime role (api_user) needs DML access; the schema/table are owned by postgres.
GRANT USAGE ON SCHEMA jobs TO api_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs.pipeline_jobs TO api_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA jobs
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO api_user;
