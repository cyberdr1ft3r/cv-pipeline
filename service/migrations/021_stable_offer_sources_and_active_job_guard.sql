-- Migration 021: stable offer source metadata and active-job guard.
-- Apply as a privileged database user. Idempotent and non-destructive.

ALTER TABLE offers.job_offers
  ADD COLUMN IF NOT EXISTS source_storage_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS source_original_filename VARCHAR(255),
  ADD COLUMN IF NOT EXISTS source_file_size BIGINT,
  ADD COLUMN IF NOT EXISTS source_sha256 CHAR(64),
  ADD COLUMN IF NOT EXISTS source_created_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN offers.job_offers.source_storage_path IS
  'Stable path relative to DATA_ROOT, e.g. offers/<offer_uuid>/original.pdf.';
COMMENT ON COLUMN offers.job_offers.source_original_filename IS
  'Original sanitized filename uploaded by the recruiter.';
COMMENT ON COLUMN offers.job_offers.source_file_size IS
  'Original offer source size in bytes.';
COMMENT ON COLUMN offers.job_offers.source_sha256 IS
  'SHA-256 checksum of the stable original offer source.';

CREATE UNIQUE INDEX IF NOT EXISTS ux_pipeline_jobs_one_active_per_offer
  ON jobs.pipeline_jobs (offer_id)
  WHERE offer_id IS NOT NULL
    AND status IN ('queued', 'pending', 'running', 'processing');

GRANT SELECT, INSERT, UPDATE, DELETE ON offers.job_offers TO api_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs.pipeline_jobs TO api_user;
