-- Initialize PostgreSQL with schemas and users for unified deployment.
-- db_bootstrap.sh supplies all values as psql variables from runtime environment.
-- Never put credentials in this file.

\if :{?api_db_password}
\else
  \echo 'api_db_password psql variable is required'
  \quit
\endif

\if :{?n8n_db_password}
\else
  \echo 'n8n_db_password psql variable is required'
  \quit
\endif

\if :{?database_name}
\else
  \echo 'database_name psql variable is required'
  \quit
\endif

SELECT format('CREATE ROLE api_user WITH LOGIN PASSWORD %L', :'api_db_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_user')
\gexec
SELECT format('ALTER ROLE api_user WITH LOGIN PASSWORD %L', :'api_db_password')
\gexec

SELECT format('CREATE ROLE n8n_user WITH LOGIN PASSWORD %L', :'n8n_db_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'n8n_user')
\gexec
SELECT format('ALTER ROLE n8n_user WITH LOGIN PASSWORD %L', :'n8n_db_password')
\gexec

-- Grant connection privileges
GRANT CONNECT ON DATABASE :"database_name" TO api_user;
GRANT CONNECT ON DATABASE :"database_name" TO n8n_user;

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
