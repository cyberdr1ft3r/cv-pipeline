# CV Pipeline deployment

Production uses `compose.prod.yml` and immutable, explicitly versioned API and frontend images. Application source is never bind-mounted into production containers. PostgreSQL and application storage use persistent named volumes; PostgreSQL, API, and frontend have no direct public ports.

## Prepare

1. Copy `deploy/env.prod.example` to `deploy/.env.prod`.
2. Replace every placeholder with independently generated secrets. Keep `API_DB_PASSWORD` URL-safe because it is embedded in `DATABASE_URL`.
3. Put a host TLS reverse proxy in front of `127.0.0.1:8080`, or deliberately change `HTTP_BIND_ADDRESS` after reviewing the firewall.
4. Authenticate Docker to the registry containing the requested image version.

The database bootstrap reads `API_DB_PASSWORD` and `N8N_DB_PASSWORD` only from the container runtime environment. Credential values are not stored in SQL. Changing those values after the database volume has already initialized requires an explicit role-password rotation.

## Deploy and verify

```sh
chmod +x deploy/*.sh
deploy/deploy.sh 2026.09.16-1
```

The deploy script validates the compose model, pulls the exact version, starts the stack, and checks the proxy, API, and frontend. A failed health check restores the previously deployed image version when one is recorded. The script records only version identifiers, never environment values.

Optional services are disabled by default:

```sh
CV_PIPELINE_VERSION=2026.09.16-1 docker compose --env-file deploy/.env.prod -f compose.prod.yml --profile watcher up -d
CV_PIPELINE_VERSION=2026.09.16-1 docker compose --env-file deploy/.env.prod -f compose.prod.yml --profile tools up -d pgadmin
```

pgAdmin binds to loopback only. The legacy Flask chatbot is not part of the production compose file.

## Roll back

```sh
deploy/rollback.sh
```

Rollback selects the previously recorded immutable image version. Database schema/data rollback is deliberately separate; take a tested database backup before deploying migrations.

## Development

`compose.dev.yml` builds from the working tree and binds service ports to loopback:

```sh
docker compose -f compose.dev.yml up -d --build
```
