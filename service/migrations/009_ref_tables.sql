-- Migration 009: Reference tables for profiles, seniorities, skills (Action 236).
-- Extends existing ref schema. Apply once as superuser. Idempotent.

CREATE SCHEMA IF NOT EXISTS ref;

CREATE TABLE IF NOT EXISTS ref.profiles (
  id          SMALLINT PRIMARY KEY,
  code        VARCHAR(50) UNIQUE NOT NULL,
  label_fr    VARCHAR(100) NOT NULL,
  is_active   BOOLEAN DEFAULT true
);

INSERT INTO ref.profiles (id, code, label_fr) VALUES
  (1,  'FullStack',       'Développeur Full Stack'),
  (2,  'DevOps',          'Ingénieur DevOps'),
  (3,  'Data',            'Data Engineer / Scientist'),
  (4,  'BusinessAnalyst', 'Business Analyst / MOA'),
  (5,  'HR',              'Ressources Humaines'),
  (6,  'Project_Manager', 'Chef de Projet'),
  (7,  'Testeur',         'Ingénieur QA / Test'),
  (8,  'Cybersecurity',   'Expert Cybersécurité'),
  (9,  'Mobile',          'Développeur Mobile'),
  (10, 'Frontend',        'Développeur Frontend'),
  (11, 'Backend',         'Développeur Backend'),
  (12, 'Cloud',           'Architecte Cloud'),
  (13, 'ERP',             'Consultant ERP')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS ref.seniorities (
  id        SMALLINT PRIMARY KEY,
  code      VARCHAR(20) UNIQUE NOT NULL,
  label_fr  VARCHAR(50) NOT NULL,
  min_years SMALLINT,
  max_years SMALLINT
);

INSERT INTO ref.seniorities (id, code, label_fr, min_years, max_years) VALUES
  (1, 'junior',   'Junior',    0,  2),
  (2, 'confirme', 'Confirmé',  3,  5),
  (3, 'senior',   'Senior',    6, 10),
  (4, 'expert',   'Expert',   11, NULL)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS ref.skills (
  id          SERIAL PRIMARY KEY,
  name        VARCHAR(100) UNIQUE NOT NULL,
  category    VARCHAR(50),
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO ref.skills (name, category) VALUES
  ('Python', 'language'),
  ('JavaScript', 'language'),
  ('TypeScript', 'language'),
  ('Java', 'language'),
  ('C#', 'language'),
  ('PHP', 'language'),
  ('React', 'framework'),
  ('Angular', 'framework'),
  ('Vue.js', 'framework'),
  ('Node.js', 'framework'),
  ('FastAPI', 'framework'),
  ('Django', 'framework'),
  ('Spring Boot', 'framework'),
  ('Docker', 'tool'),
  ('Kubernetes', 'tool'),
  ('Git', 'tool'),
  ('Jenkins', 'tool'),
  ('Jira', 'tool'),
  ('PostgreSQL', 'database'),
  ('MySQL', 'database'),
  ('MongoDB', 'database'),
  ('Redis', 'database'),
  ('AWS', 'cloud'),
  ('Azure', 'cloud'),
  ('GCP', 'cloud'),
  ('Agile', 'methodology'),
  ('Scrum', 'methodology'),
  ('CI/CD', 'methodology')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS candidates.candidate_skills (
  candidate_id  UUID NOT NULL
                REFERENCES candidates.profiles(id)
                ON DELETE CASCADE,
  skill_id      INTEGER NOT NULL
                REFERENCES ref.skills(id)
                ON DELETE CASCADE,
  level         VARCHAR(20) DEFAULT 'known'
                CHECK (level IN (
                  'known', 'intermediate',
                  'advanced', 'expert'
                )),
  PRIMARY KEY (candidate_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_candidate_skills_skill_id
  ON candidates.candidate_skills(skill_id);

ALTER TABLE candidates.profiles
  ADD COLUMN IF NOT EXISTS profile_id SMALLINT
    REFERENCES ref.profiles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS seniority_id SMALLINT
    REFERENCES ref.seniorities(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_candidates_profile_id
  ON candidates.profiles(profile_id);
CREATE INDEX IF NOT EXISTS idx_candidates_seniority_id
  ON candidates.profiles(seniority_id);

UPDATE candidates.profiles c
SET profile_id = p.id
FROM ref.profiles p
WHERE LOWER(c.profile) = LOWER(p.code)
  AND c.profile IS NOT NULL
  AND c.profile_id IS NULL;

UPDATE candidates.profiles c
SET seniority_id = s.id
FROM ref.seniorities s
WHERE LOWER(c.seniority) = LOWER(s.code)
  AND c.seniority IS NOT NULL
  AND c.seniority_id IS NULL;

GRANT SELECT ON ref.profiles TO api_user;
GRANT SELECT ON ref.seniorities TO api_user;
GRANT SELECT, INSERT ON ref.skills TO api_user;
GRANT SELECT, INSERT, DELETE
  ON candidates.candidate_skills TO api_user;
GRANT USAGE, SELECT ON SEQUENCE ref.skills_id_seq TO api_user;
