-- Backfill format phase history for appearances already marked (envoye_client, etc.)
-- when history rows were missing because update_appearance_status did not insert them.

INSERT INTO candidates.appearance_status_history
  (appearance_id, phase, status_id, status_code, changed_at, changed_by)
SELECT oa.id, 'format', oa.format_status_id, fs.code, oa.format_status_changed_at, NULL
FROM candidates.offer_appearances oa
JOIN ref.format_statuses fs ON fs.id = oa.format_status_id
WHERE oa.format_status_id != 1
  AND oa.format_status_changed_at IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM candidates.appearance_status_history h
    WHERE h.appearance_id = oa.id
      AND h.phase = 'format'
      AND h.status_id = oa.format_status_id
  );
