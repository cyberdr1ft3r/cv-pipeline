-- Migration 008: Candidate CRM schema (Action 235).
-- Apply once as superuser. Idempotent.

CREATE SCHEMA IF NOT EXISTS candidates;

CREATE TABLE IF NOT EXISTS candidates.profiles (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cv_filename       VARCHAR(255) NOT NULL,
  cv_sftp_path      VARCHAR(500) NOT NULL,
  profile           VARCHAR(50),
  seniority         VARCHAR(20),
  full_name         VARCHAR(255) NOT NULL,
  email             VARCHAR(255),
  phone             VARCHAR(50),
  location          VARCHAR(100),
  open_to_work      BOOLEAN DEFAULT true,
  availability_date DATE,
  current_salary    DECIMAL(10,2),
  expected_salary   DECIMAL(10,2),
  salary_currency   VARCHAR(3) DEFAULT 'MAD',
  onboarded         BOOLEAN DEFAULT false,
  onboarding_date   DATE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at        TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_cv_path
  ON candidates.profiles(cv_sftp_path)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_candidates_profile_seniority
  ON candidates.profiles(profile, seniority);
CREATE INDEX IF NOT EXISTS idx_candidates_email
  ON candidates.profiles(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_candidates_open_to_work
  ON candidates.profiles(open_to_work);
CREATE INDEX IF NOT EXISTS idx_candidates_full_name
  ON candidates.profiles(full_name);

CREATE TABLE IF NOT EXISTS candidates.notes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID NOT NULL
                REFERENCES candidates.profiles(id)
                ON DELETE CASCADE,
  author_id     UUID REFERENCES auth.users(id)
                ON DELETE SET NULL,
  author_name   VARCHAR(255) NOT NULL,
  author_role   VARCHAR(20) NOT NULL,
  content       TEXT NOT NULL,
  note_type     VARCHAR(20) DEFAULT 'general'
                CHECK (note_type IN (
                  'general','interview','technical',
                  'behavioral','salary','availability'
                )),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_candidate_id
  ON candidates.notes(candidate_id);

CREATE TABLE IF NOT EXISTS candidates.offer_appearances (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id    UUID NOT NULL
                  REFERENCES candidates.profiles(id)
                  ON DELETE CASCADE,
  offer_id        UUID NOT NULL
                  REFERENCES offers.job_offers(id)
                  ON DELETE CASCADE,
  job_id          VARCHAR(36),
  matching_score  DECIMAL(5,2),
  final_score     DECIMAL(5,2),
  rank            INTEGER,
  decision        VARCHAR(20) DEFAULT 'pending'
                  CHECK (decision IN (
                    'pending','shortlisted','contacted',
                    'interviewed','offered',
                    'hired','rejected'
                  )),
  decision_notes  TEXT,
  decision_at     TIMESTAMPTZ,
  decision_by     UUID REFERENCES auth.users(id)
                  ON DELETE SET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(candidate_id, offer_id)
);

CREATE INDEX IF NOT EXISTS idx_appearances_candidate_id
  ON candidates.offer_appearances(candidate_id);
CREATE INDEX IF NOT EXISTS idx_appearances_offer_id
  ON candidates.offer_appearances(offer_id);
CREATE INDEX IF NOT EXISTS idx_appearances_decision
  ON candidates.offer_appearances(decision);

GRANT USAGE ON SCHEMA candidates TO api_user;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA candidates TO api_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA candidates
  TO api_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA candidates
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
  TO api_user;
