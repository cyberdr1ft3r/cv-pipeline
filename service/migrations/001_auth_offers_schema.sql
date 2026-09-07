-- Migration 001: auth and offers schemas
-- Run once against cv_pipeline database.
-- Idempotent: uses IF NOT EXISTS / DO $$ everywhere safe.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ── Schemas ───────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS offers;

-- ── auth.users ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth.users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email           VARCHAR(255) UNIQUE NOT NULL,
  full_name       VARCHAR(255) NOT NULL,
  role            VARCHAR(20) NOT NULL DEFAULT 'sourcer'
                  CONSTRAINT users_role_check
                    CHECK (role IN ('sourcer', 'recruiter', 'admin')),
  hashed_password VARCHAR(255) NOT NULL,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  last_login_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email
  ON auth.users(email)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_users_role
  ON auth.users(role);

-- ── offers.job_offers ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS offers.job_offers (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title            VARCHAR(200) NOT NULL,
  description      TEXT NOT NULL,
  required_skills  JSONB NOT NULL DEFAULT '[]',
  experience_level VARCHAR(50),
  location         VARCHAR(100),
  salary_range     VARCHAR(50),
  status           VARCHAR(20) NOT NULL DEFAULT 'open'
                   CONSTRAINT job_offers_status_check
                     CHECK (status IN ('open', 'in_progress', 'closed', 'archived')),
  created_by       UUID NOT NULL,   -- ref: auth.users.id (by value, no FK across schemas)
  assigned_to      UUID,            -- ref: auth.users.id (by value)
  file_path        VARCHAR(500),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_job_offers_status
  ON offers.job_offers(status)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_job_offers_created_by
  ON offers.job_offers(created_by)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_job_offers_assigned_to
  ON offers.job_offers(assigned_to)
  WHERE deleted_at IS NULL;
