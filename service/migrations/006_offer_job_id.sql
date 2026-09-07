-- Migration 006 — ensure offers.job_offers.job_id is indexed, FK-linked and writable.
--
-- NOTE: the `job_id` column already exists (added informally before this migration),
-- so the ADD COLUMN below is effectively a no-op kept only for fresh installs.
-- This migration is idempotent and safe to re-run.

-- 1. Column (no-op if it already exists).
ALTER TABLE offers.job_offers
  ADD COLUMN IF NOT EXISTS job_id VARCHAR(36);

-- 2. Foreign key to jobs.pipeline_jobs(id). Added guardedly because ADD COLUMN
--    IF NOT EXISTS skips the inline REFERENCES clause when the column pre-exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_job_offers_job_id'
    ) THEN
        ALTER TABLE offers.job_offers
            ADD CONSTRAINT fk_job_offers_job_id
            FOREIGN KEY (job_id) REFERENCES jobs.pipeline_jobs(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 3. Index for dashboard / detail joins.
CREATE INDEX IF NOT EXISTS idx_job_offers_job_id
  ON offers.job_offers(job_id);

-- 4. Pipeline launch updates job_id + status_id via api_user.
GRANT UPDATE ON offers.job_offers TO api_user;
