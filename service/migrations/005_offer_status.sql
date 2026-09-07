-- Migration 005: offer status lifecycle redesign.
-- Introduces a reference table (ref.offer_statuses) and a status_id FK on
-- offers.job_offers. The legacy text `status` column is kept for now (deprecated).
-- Apply once against cv_pipeline as a superuser (api_user lacks CREATE SCHEMA);
-- grants below hand the required privileges to api_user. Idempotent.

CREATE SCHEMA IF NOT EXISTS ref;

-- Reference table for offer statuses
CREATE TABLE IF NOT EXISTS ref.offer_statuses (
  id          SMALLINT PRIMARY KEY,
  code        VARCHAR(30) UNIQUE NOT NULL,
  label_fr    VARCHAR(50) NOT NULL,
  description TEXT,
  sort_order  SMALLINT NOT NULL,
  visible_to  VARCHAR(20) NOT NULL
              CHECK (visible_to IN ('all','recruiter_only'))
);

INSERT INTO ref.offer_statuses
  (id, code, label_fr, description, sort_order, visible_to)
VALUES
  (1, 'open',         'Ouverte',        'Offre créée, non assignée',               1, 'all'),
  (2, 'assigned',     'Assignée',       'Assignée à un sourceur',                  2, 'all'),
  (3, 'in_progress',  'En cours',       'Pipeline en cours d''exécution',          3, 'all'),
  (4, 'matched',      'Matchée',        'Matching terminé, résultats disponibles', 4, 'all'),
  (5, 'final_result', 'Résultat final', 'Résultat final généré par le recruteur',  5, 'recruiter_only'),
  (6, 'formatted',    'Formatée',       'CVs formatés par le recruteur',           6, 'recruiter_only'),
  (7, 'archived',     'Archivée',       'Offre archivée',                          7, 'all')
ON CONFLICT (id) DO UPDATE
  SET code = EXCLUDED.code,
      label_fr = EXCLUDED.label_fr,
      description = EXCLUDED.description,
      sort_order = EXCLUDED.sort_order,
      visible_to = EXCLUDED.visible_to;

GRANT USAGE ON SCHEMA ref TO api_user;
GRANT SELECT ON ref.offer_statuses TO api_user;

-- Add status_id FK to offers table
ALTER TABLE offers.job_offers
  ADD COLUMN IF NOT EXISTS status_id SMALLINT
    REFERENCES ref.offer_statuses(id) DEFAULT 1;

-- Migrate existing status text values to status_id
UPDATE offers.job_offers SET status_id = 1 WHERE status = 'open' OR status IS NULL;
UPDATE offers.job_offers SET status_id = 2 WHERE status = 'in_progress';
UPDATE offers.job_offers SET status_id = 4 WHERE status = 'closed';
UPDATE offers.job_offers SET status_id = 7 WHERE status = 'archived';

-- Keep old status column for now (deprecate later).
