-- Manual operator helper: inspect and optionally cancel duplicate active jobs.
-- This file is NOT part of automatic migrations. Run manually only after review.

-- 1) Inspect duplicate active jobs per offer.
SELECT
  offer_id,
  COUNT(*) AS active_jobs,
  ARRAY_AGG(id ORDER BY created_at ASC) AS job_ids_oldest_first,
  ARRAY_AGG(status ORDER BY created_at ASC) AS statuses_oldest_first
FROM jobs.pipeline_jobs
WHERE offer_id IS NOT NULL
  AND status IN ('queued', 'pending', 'running', 'processing')
GROUP BY offer_id
HAVING COUNT(*) > 1
ORDER BY active_jobs DESC, offer_id;

-- 2) Optional cleanup. Change confirmed.value to true only after operator approval.
WITH confirmed(value) AS (VALUES (false)),
ranked AS (
  SELECT
    j.id,
    j.offer_id,
    ROW_NUMBER() OVER (
      PARTITION BY j.offer_id
      ORDER BY
        CASE j.status
          WHEN 'running' THEN 1
          WHEN 'processing' THEN 2
          WHEN 'queued' THEN 3
          WHEN 'pending' THEN 4
          ELSE 9
        END,
        j.created_at ASC
    ) AS keep_rank
  FROM jobs.pipeline_jobs j
  WHERE j.offer_id IS NOT NULL
    AND j.status IN ('queued', 'pending', 'running', 'processing')
)
UPDATE jobs.pipeline_jobs j
SET status = 'failed',
    stage = 'failed',
    error_message = COALESCE(j.error_message, 'Doublon actif annulé par nettoyage opérateur'),
    completed_at = COALESCE(j.completed_at, NOW()),
    updated_at = NOW()
FROM ranked r, confirmed c
WHERE c.value = true
  AND j.id = r.id
  AND r.keep_rank > 1
RETURNING j.offer_id, j.id, j.status, j.error_message;
