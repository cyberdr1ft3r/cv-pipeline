-- Migration 012: separate sourcer/recruiter notes on offer appearances (Action 254).
-- Idempotent.

ALTER TABLE candidates.offer_appearances
  ADD COLUMN IF NOT EXISTS sourcer_note TEXT,
  ADD COLUMN IF NOT EXISTS recruiter_note TEXT;

-- Legacy decision_notes (Action 253) → recruiter_note when role columns are empty.
UPDATE candidates.offer_appearances
SET recruiter_note = decision_notes
WHERE decision_notes IS NOT NULL
  AND TRIM(decision_notes) <> ''
  AND (recruiter_note IS NULL OR TRIM(recruiter_note) = '')
  AND (sourcer_note IS NULL OR TRIM(sourcer_note) = '');
