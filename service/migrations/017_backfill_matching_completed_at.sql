-- Action 284: backfill matching_completed_at from legacy completed_at

UPDATE jobs.pipeline_jobs
SET matching_completed_at = completed_at
WHERE stage = 'matching_complete'
  AND matching_completed_at IS NULL
  AND completed_at IS NOT NULL;
