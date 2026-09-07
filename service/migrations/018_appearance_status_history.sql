-- Action 285: append-only status change history for KPI accuracy

CREATE TABLE IF NOT EXISTS candidates.appearance_status_history (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appearance_id UUID NOT NULL
                REFERENCES candidates.offer_appearances(id)
                ON DELETE CASCADE,
  phase         VARCHAR(20) NOT NULL
                CHECK (phase IN ('matching','final','format')),
  status_id     SMALLINT NOT NULL,
  status_code   VARCHAR(30) NOT NULL,
  changed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  changed_by    UUID REFERENCES auth.users(id)
                ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_appearance_status_history
  ON candidates.appearance_status_history(appearance_id, phase, status_id);

GRANT SELECT, INSERT
  ON candidates.appearance_status_history TO api_user;

-- Backfill format phase (best-effort from current status + changed_at)
INSERT INTO candidates.appearance_status_history
  (appearance_id, phase, status_id, status_code, changed_at)
SELECT a.id, 'format', a.format_status_id, fs.code, a.format_status_changed_at
FROM candidates.offer_appearances a
JOIN ref.format_statuses fs ON fs.id = a.format_status_id
WHERE a.format_status_id != 1
  AND a.format_status_changed_at IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM candidates.appearance_status_history h
    WHERE h.appearance_id = a.id AND h.phase = 'format'
  );

-- Backfill matching phase
INSERT INTO candidates.appearance_status_history
  (appearance_id, phase, status_id, status_code, changed_at)
SELECT a.id, 'matching', a.matching_status_id, ms.code, a.matching_status_changed_at
FROM candidates.offer_appearances a
JOIN ref.matching_statuses ms ON ms.id = a.matching_status_id
WHERE a.matching_status_id != 1
  AND a.matching_status_changed_at IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM candidates.appearance_status_history h
    WHERE h.appearance_id = a.id AND h.phase = 'matching'
  );

-- Backfill final phase
INSERT INTO candidates.appearance_status_history
  (appearance_id, phase, status_id, status_code, changed_at)
SELECT a.id, 'final', a.final_status_id, fs.code, a.final_status_changed_at
FROM candidates.offer_appearances a
JOIN ref.final_statuses fs ON fs.id = a.final_status_id
WHERE a.final_status_id != 1
  AND a.final_status_changed_at IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM candidates.appearance_status_history h
    WHERE h.appearance_id = a.id AND h.phase = 'final'
  );
