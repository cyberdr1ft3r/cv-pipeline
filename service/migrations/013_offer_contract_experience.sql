-- Migration 013: Contract types + experience ranges reference tables (Action 280).
-- Apply once as superuser. Idempotent.

CREATE TABLE IF NOT EXISTS ref.contract_types (
  id          SMALLINT PRIMARY KEY,
  code        VARCHAR(20) UNIQUE NOT NULL,
  label_fr    VARCHAR(50) NOT NULL,
  is_active   BOOLEAN DEFAULT true
);

INSERT INTO ref.contract_types (id, code, label_fr) VALUES
  (1, 'CDI',        'CDI'),
  (2, 'CDD',        'CDD'),
  (3, 'Freelance',  'Freelance / Mission'),
  (4, 'Stage',      'Stage'),
  (5, 'Alternance', 'Alternance'),
  (6, 'Regie',      E'R\u00e9gie')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS ref.experience_ranges (
  id        SERIAL PRIMARY KEY,
  min_years DECIMAL(4,1),
  max_years DECIMAL(4,1),
  UNIQUE NULLS NOT DISTINCT (min_years, max_years)
);

INSERT INTO ref.experience_ranges (min_years, max_years) VALUES
  (0,    2   ),
  (3,    5   ),
  (6,    10  ),
  (11,   NULL),
  (2,    NULL),
  (3,    NULL),
  (4,    NULL),
  (5,    NULL),
  (6,    NULL),
  (NULL, 2   ),
  (NULL, 3   ),
  (NULL, 4   ),
  (2,    5   ),
  (4,    9   ),
  (3,    7   ),
  (5,    10  )
ON CONFLICT (min_years, max_years) DO NOTHING;

GRANT SELECT ON ref.contract_types TO api_user;
GRANT SELECT, INSERT ON ref.experience_ranges TO api_user;
GRANT USAGE, SELECT ON SEQUENCE ref.experience_ranges_id_seq TO api_user;

ALTER TABLE offers.job_offers
  ADD COLUMN IF NOT EXISTS contract_type_id SMALLINT
    REFERENCES ref.contract_types(id) DEFAULT 1,
  ADD COLUMN IF NOT EXISTS experience_range_id INTEGER
    REFERENCES ref.experience_ranges(id);

UPDATE offers.job_offers
  SET contract_type_id = 1
  WHERE contract_type_id IS NULL;

UPDATE offers.job_offers o
  SET experience_range_id = r.id
  FROM ref.experience_ranges r
  WHERE LOWER(COALESCE(o.experience_level, '')) IN ('junior')
    AND r.min_years = 0 AND r.max_years = 2
    AND o.experience_range_id IS NULL;

UPDATE offers.job_offers o
  SET experience_range_id = r.id
  FROM ref.experience_ranges r
  WHERE LOWER(COALESCE(o.experience_level, '')) IN ('confirmé', 'confirme')
    AND r.min_years = 3 AND r.max_years = 5
    AND o.experience_range_id IS NULL;

UPDATE offers.job_offers o
  SET experience_range_id = r.id
  FROM ref.experience_ranges r
  WHERE LOWER(COALESCE(o.experience_level, '')) = 'senior'
    AND r.min_years = 6 AND r.max_years = 10
    AND o.experience_range_id IS NULL;

UPDATE offers.job_offers o
  SET experience_range_id = r.id
  FROM ref.experience_ranges r
  WHERE LOWER(COALESCE(o.experience_level, '')) = 'expert'
    AND r.min_years = 11 AND r.max_years IS NULL
    AND o.experience_range_id IS NULL;
