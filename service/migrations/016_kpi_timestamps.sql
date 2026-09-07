-- Action 283: KPI phase timestamps on appearances and pipeline jobs

ALTER TABLE candidates.offer_appearances
  ADD COLUMN IF NOT EXISTS matching_status_changed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS final_status_changed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS format_status_changed_at TIMESTAMPTZ;

ALTER TABLE jobs.pipeline_jobs
  ADD COLUMN IF NOT EXISTS matching_completed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS final_completed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS format_completed_at TIMESTAMPTZ;
