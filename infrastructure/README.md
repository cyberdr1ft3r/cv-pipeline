# Infrastructure

Deployment and infrastructure configuration files for the CV Pipeline project.

## Files

### `db_init.sql`
PostgreSQL initialization SQL invoked by `db_bootstrap.sh` on the first start of a new database volume.

**Purpose:**
- Creates dedicated database users for API and n8n
- Sets up isolated schemas (`api_schema` and `n8n_schema`)
- Configures permissions and access control
- Enables data isolation while sharing a single database

**Users Created:**
- `api_user` - FastAPI backend (uses `api_schema`)
- `n8n_user` - n8n workflow automation (uses `n8n_schema`)

**Runtime configuration:**
Passwords are required environment variables passed by Compose into the PostgreSQL container and then into `psql` variables by `db_bootstrap.sh`:
- `API_DB_PASSWORD` - api_user password
- `N8N_DB_PASSWORD` - n8n_user password

No password belongs in `db_init.sql`. Production values must be strong, independently generated secrets and must be rotated through an explicit database operation after the volume has initialized.

## How It Works

1. PostgreSQL container starts
2. Runs `/docker-entrypoint-initdb.d/00_bootstrap.sh`
3. The bootstrap passes runtime credentials to `db_init.sql` without printing them, then applies numbered migrations
4. API and n8n containers connect with their respective credentials
5. Data isolation via schemas enforces separation

## Mounted in Docker

In `docker-compose.yml`:
```yaml
volumes:
  - ./infrastructure/db_bootstrap.sh:/docker-entrypoint-initdb.d/00_bootstrap.sh:ro
  - ./infrastructure/db_init.sql:/sql/db_init.sql:ro
  - ./service/migrations:/sql/migrations:ro
```

This mount point is standard for PostgreSQL Docker images - scripts in `/docker-entrypoint-initdb.d/` run on first container initialization.

## Database Structure

```
cv_pipeline/
├── api_schema/          (API data)
│   └── owned by api_user
├── n8n_schema/          (n8n workflows)
│   └── owned by n8n_user
└── public/              (shared - both users have access)
```

## Adding New Schemas

To add schema for another service:

1. Add parameterized role creation in `db_init.sql`
2. Create schema and grant privileges
3. Update `.env` with new credentials
4. Update `docker-compose.yml` to pass credentials
