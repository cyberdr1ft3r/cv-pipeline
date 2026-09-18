#!/bin/bash
# Runs automatically on the FIRST postgres start (empty data volume only).
# Applies the base schema (roles/schemas/grants) then every numbered migration
# in order, as the postgres superuser. All SQL is idempotent (IF NOT EXISTS),
# but this only executes once on a fresh volume.
#
# Wired via docker-compose.hub.yml:
#   /docker-entrypoint-initdb.d/00_bootstrap.sh  (this file)
#   /sql/db_init.sql                             (roles/schemas/grants)
#   /sql/migrations/*.sql                        (001..NNN migrations)
set -euo pipefail

: "${API_DB_PASSWORD:?Set API_DB_PASSWORD in the runtime environment}"
: "${N8N_DB_PASSWORD:?Set N8N_DB_PASSWORD in the runtime environment}"

PSQL=(
  psql
  -v ON_ERROR_STOP=1
  -v "api_db_password=$API_DB_PASSWORD"
  -v "n8n_db_password=$N8N_DB_PASSWORD"
  -v "database_name=$POSTGRES_DB"
  --username "$POSTGRES_USER"
  --dbname "$POSTGRES_DB"
)

echo "[db-bootstrap] applying base schema (db_init.sql)"
"${PSQL[@]}" -f /sql/db_init.sql

echo "[db-bootstrap] applying migrations in order"
for f in $(ls -1 /sql/migrations/*.sql | sort); do
  echo "[db-bootstrap]   -> $(basename "$f")"
  "${PSQL[@]}" -f "$f"
done

echo "[db-bootstrap] schema ready"
