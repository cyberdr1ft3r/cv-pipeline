-- Migration 002: add session_id, offer_sftp_path, job_id to job_offers;
--               create offer_assignments table.
-- Run after 001_auth_offers_schema.sql. Idempotent.

ALTER TABLE offers.job_offers
  ADD COLUMN IF NOT EXISTS session_id    VARCHAR(50),
  ADD COLUMN IF NOT EXISTS offer_sftp_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS job_id        VARCHAR(36);

-- Partial unique index so NULLs are not considered duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_offers_session_id
  ON offers.job_offers(session_id)
  WHERE session_id IS NOT NULL;

-- Assignment history (append-only; one active row per offer)
CREATE TABLE IF NOT EXISTS offers.offer_assignments (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id     UUID NOT NULL,        -- ref: offers.job_offers.id (by value)
  assigned_to  UUID NOT NULL,        -- ref: auth.users.id (by value)
  assigned_by  UUID NOT NULL,        -- ref: auth.users.id (by value)
  assigned_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_active    BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_assignments_offer_id
  ON offers.offer_assignments(offer_id)
  WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_assignments_assigned_to
  ON offers.offer_assignments(assigned_to)
  WHERE is_active = true;
