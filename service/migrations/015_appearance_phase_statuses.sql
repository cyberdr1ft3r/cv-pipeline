-- Action 282: Phase-specific candidate statuses + unreliability flags

-- Matching phase statuses
CREATE TABLE IF NOT EXISTS ref.matching_statuses (
  id        SMALLINT PRIMARY KEY,
  code      VARCHAR(30) UNIQUE NOT NULL,
  label_fr  VARCHAR(50) NOT NULL,
  sort_order SMALLINT NOT NULL
);
INSERT INTO ref.matching_statuses (id, code, label_fr, sort_order) VALUES
  (1, 'en_attente',    'En attente',     1),
  (2, 'preselectionne','Présélectionné', 2),
  (3, 'contacte',      'Contacté',       3)
ON CONFLICT (id) DO NOTHING;

-- Final result phase statuses
CREATE TABLE IF NOT EXISTS ref.final_statuses (
  id        SMALLINT PRIMARY KEY,
  code      VARCHAR(30) UNIQUE NOT NULL,
  label_fr  VARCHAR(50) NOT NULL,
  sort_order SMALLINT NOT NULL
);
INSERT INTO ref.final_statuses (id, code, label_fr, sort_order) VALUES
  (1, 'en_attente',  'En attente',  1),
  (2, 'interviewe',  'Interviewé',  2),
  (3, 'valide',      'Validé',      3),
  (4, 'non_valide',  'Non validé',  4)
ON CONFLICT (id) DO NOTHING;

-- Format/client phase statuses
CREATE TABLE IF NOT EXISTS ref.format_statuses (
  id        SMALLINT PRIMARY KEY,
  code      VARCHAR(30) UNIQUE NOT NULL,
  label_fr  VARCHAR(50) NOT NULL,
  sort_order SMALLINT NOT NULL,
  triggers_flag BOOLEAN DEFAULT false
);
INSERT INTO ref.format_statuses (id, code, label_fr, sort_order, triggers_flag) VALUES
  (1, 'en_attente',          'En attente',                1, false),
  (2, 'envoye_client',       'Envoyé au client',          2, false),
  (3, 'valide_client',       'Validé par le client',      3, false),
  (4, 'non_valide_client',   'Non validé par le client',  4, false),
  (5, 'offre_faite',         'Offre faite',                5, false),
  (6, 'recrute',             'Recruté',                    6, false),
  (7, 'non_integre',         'Non intégré',                7, true),
  (8, 'rejete',              'Rejeté',                     8, false)
ON CONFLICT (id) DO NOTHING;

GRANT SELECT ON ref.matching_statuses TO api_user;
GRANT SELECT ON ref.final_statuses TO api_user;
GRANT SELECT ON ref.format_statuses TO api_user;

-- Add phase status FK columns to offer_appearances
ALTER TABLE candidates.offer_appearances
  ADD COLUMN IF NOT EXISTS matching_status_id SMALLINT
    REFERENCES ref.matching_statuses(id) DEFAULT 1,
  ADD COLUMN IF NOT EXISTS final_status_id SMALLINT
    REFERENCES ref.final_statuses(id) DEFAULT 1,
  ADD COLUMN IF NOT EXISTS format_status_id SMALLINT
    REFERENCES ref.format_statuses(id) DEFAULT 1;

-- Migrate existing 'decision' values to matching_status_id
UPDATE candidates.offer_appearances
  SET matching_status_id = CASE decision
    WHEN 'pending' THEN 1
    WHEN 'shortlisted' THEN 2
    WHEN 'contacted' THEN 3
    ELSE 1
  END
WHERE matching_status_id IS NULL;

-- Unreliability flags table
CREATE TABLE IF NOT EXISTS candidates.unreliability_flags (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID NOT NULL
                REFERENCES candidates.profiles(id)
                ON DELETE CASCADE,
  offer_id      UUID REFERENCES offers.job_offers(id)
                ON DELETE SET NULL,
  appearance_id UUID REFERENCES candidates.offer_appearances(id)
                ON DELETE SET NULL,
  reason        TEXT NOT NULL,
  flagged_by    UUID REFERENCES auth.users(id)
                ON DELETE SET NULL,
  flagged_by_name VARCHAR(255),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at   TIMESTAMPTZ,
  resolved_by   UUID REFERENCES auth.users(id)
                ON DELETE SET NULL,
  resolved_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_unreliability_candidate
  ON candidates.unreliability_flags(candidate_id)
  WHERE resolved_at IS NULL;

GRANT SELECT, INSERT, UPDATE
  ON candidates.unreliability_flags TO api_user;
