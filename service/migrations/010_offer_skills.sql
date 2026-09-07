-- Migration 010: Link offer required skills to ref.skills via bridge table (Action 248).
-- Apply once as superuser. Idempotent.

CREATE TABLE IF NOT EXISTS offers.offer_skills (
  offer_id    UUID NOT NULL
              REFERENCES offers.job_offers(id)
              ON DELETE CASCADE,
  skill_id    INTEGER NOT NULL
              REFERENCES ref.skills(id)
              ON DELETE CASCADE,
  is_required BOOLEAN DEFAULT true,
  PRIMARY KEY (offer_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_offer_skills_skill_id
  ON offers.offer_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_offer_skills_offer_id
  ON offers.offer_skills(offer_id);

GRANT SELECT, INSERT, DELETE
  ON offers.offer_skills TO api_user;

-- Backfill existing offers from required_skills JSONB (best-effort per skill string).
DO $$
DECLARE
  offer_rec RECORD;
  skill_text TEXT;
BEGIN
  FOR offer_rec IN
    SELECT id, required_skills
    FROM offers.job_offers
    WHERE deleted_at IS NULL
      AND required_skills IS NOT NULL
      AND jsonb_typeof(required_skills) = 'array'
      AND jsonb_array_length(required_skills) > 0
  LOOP
    FOR skill_text IN
      SELECT trim(both from elem::text)
      FROM jsonb_array_elements_text(offer_rec.required_skills) AS elem
    LOOP
      IF skill_text IS NULL OR skill_text = '' THEN
        CONTINUE;
      END IF;
      INSERT INTO ref.skills (name, category)
      VALUES (skill_text, 'other')
      ON CONFLICT (name) DO NOTHING;
      INSERT INTO offers.offer_skills (offer_id, skill_id, is_required)
      SELECT offer_rec.id, s.id, true
      FROM ref.skills s
      WHERE s.name = skill_text
      ON CONFLICT (offer_id, skill_id) DO NOTHING;
    END LOOP;
  END LOOP;
END $$;
