-- Migration 004: audit schema + activity_log table.
-- Dedicated append-only audit trail replacing the fragile multi-table activity merge.
-- Run once against cv_pipeline. Idempotent (IF NOT EXISTS everywhere).
-- Must be applied as a superuser (api_user lacks CREATE SCHEMA); grants below
-- hand the necessary privileges to api_user.

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.activity_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type  VARCHAR(50) NOT NULL,
  -- offer_created, offer_assigned, offer_deleted,
  -- pipeline_launched, pipeline_completed, pipeline_failed,
  -- user_created, user_updated, user_deactivated,
  -- user_reactivated, user_deleted, user_login
  description TEXT NOT NULL,
  actor_id    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  actor_name  VARCHAR(255),
  target_id   VARCHAR(100),
  target_type VARCHAR(50),
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_created_at
  ON audit.activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_event_type
  ON audit.activity_log(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_log_actor_id
  ON audit.activity_log(actor_id);

GRANT USAGE ON SCHEMA audit TO api_user;
GRANT SELECT, INSERT ON audit.activity_log TO api_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA audit TO api_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit
  GRANT SELECT, INSERT ON TABLES TO api_user;
