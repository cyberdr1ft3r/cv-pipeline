# CV Pipeline deployment

Production uses `compose.prod.yml` and immutable, explicitly versioned API and frontend images. Application source is never bind-mounted into production containers. PostgreSQL and application storage use persistent named volumes; PostgreSQL, API, and frontend have no direct public ports.

## Prepare

1. Copy `deploy/env.prod.example` to `deploy/.env.prod`.
2. Replace every placeholder with independently generated secrets. Keep `API_DB_PASSWORD` URL-safe because it is embedded in `DATABASE_URL`.
3. Put a host TLS reverse proxy in front of `127.0.0.1:8080`. The host proxy must replace (not append untrusted client input to) `X-Forwarded-For`, `X-Real-IP`, and `X-Forwarded-Proto` before forwarding requests.
4. Authenticate Docker to the registry containing the requested image version.

The database bootstrap reads `API_DB_PASSWORD` and `N8N_DB_PASSWORD` only from the container runtime environment. Credential values are not stored in SQL. Changing those values after the database volume has already initialized requires an explicit role-password rotation.

## Deploy and verify

```sh
chmod +x deploy/*.sh
deploy/deploy.sh 2026.09.16-1
```

The deploy script validates the compose model, pulls the exact version, and starts PostgreSQL, API, watcher, frontend, and proxy. It checks the HTTP path and confirms every required container is running, is not restarting, and is healthy when a health check is defined. A failed check restores the previously deployed image version when one is recorded. The script records only version identifiers, never environment values.

The staging watcher is required application functionality and starts during every normal production deployment. pgAdmin is the only optional service:

```sh
CV_PIPELINE_VERSION=2026.09.16-1 docker compose --env-file deploy/.env.prod -f compose.prod.yml --profile tools up -d pgadmin
```

pgAdmin binds to loopback only. The legacy Flask chatbot is not part of the production compose file.

## Proxy trust boundary

The production API accepts proxy headers because it has no published host port and is reachable only from the controlled inner proxy on the private Docker `app` network. The inner proxy preserves the forwarding headers supplied by the host TLS proxy, so HTTPS remains `https` and FastAPI/Uvicorn resolves `request.client.host` to the original client address for rate limiting and audit logging.

Keep the inner proxy bound to `127.0.0.1`, expose only the host TLS proxy to the Internet, and configure that host proxy to overwrite the forwarding headers it receives from clients. Do not publish the API container port or expose the inner proxy directly: doing either would let an untrusted client supply headers that the API is configured to trust.

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
