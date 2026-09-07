-- Initialize PostgreSQL with schemas and users for unified deployment
-- This ensures API and n8n share one database but with separate schemas

-- Create dedicated users
DO $$ 
BEGIN
    -- API user
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_user') THEN
        CREATE ROLE api_user WITH LOGIN PASSWORD 'api_password_change_in_prod';
    END IF;
    
    -- n8n user
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'n8n_user') THEN
        CREATE ROLE n8n_user WITH LOGIN PASSWORD 'n8n_password_change_in_prod';
    END IF;
END
$$;

-- Grant connection privileges
GRANT CONNECT ON DATABASE cv_pipeline TO api_user;
GRANT CONNECT ON DATABASE cv_pipeline TO n8n_user;

-- Grant default privileges on public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO api_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO api_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO n8n_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO n8n_user;

-- Create schemas for data isolation
CREATE SCHEMA IF NOT EXISTS api_schema AUTHORIZATION api_user;
CREATE SCHEMA IF NOT EXISTS n8n_schema AUTHORIZATION n8n_user;

-- Grant schema access and privileges
GRANT USAGE ON SCHEMA api_schema TO api_user;
GRANT CREATE ON SCHEMA api_schema TO api_user;
GRANT USAGE ON SCHEMA n8n_schema TO n8n_user;
GRANT CREATE ON SCHEMA n8n_schema TO n8n_user;

GRANT USAGE ON SCHEMA public TO api_user, n8n_user;

-- Set search path for users
ALTER USER api_user SET search_path TO api_schema, public;
ALTER USER n8n_user SET search_path TO n8n_schema, public;

-- Grant privileges on existing tables in public schema
GRANT ALL ON ALL TABLES IN SCHEMA public TO api_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO n8n_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO api_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO n8n_user;

-- Grant rights to create objects in public schema (for migrations)
GRANT CREATE ON SCHEMA public TO api_user;
GRANT CREATE ON SCHEMA public TO n8n_user;
