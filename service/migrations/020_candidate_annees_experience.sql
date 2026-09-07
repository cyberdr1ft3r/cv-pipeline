-- Migration 020: Persist years of experience on candidate profiles (Action 299).
-- Apply once as superuser. Idempotent.

ALTER TABLE candidates.profiles
  ADD COLUMN IF NOT EXISTS annees_experience VARCHAR(50);

COMMENT ON COLUMN candidates.profiles.annees_experience IS
  'Formatted years from CV extraction, e.g. ''5 ans'' (profil_resume.annees_experience)';
