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

## Google Drive service-account credentials

The Drive importer authenticates with a Google service account that holds Viewer
access to the Shared Drive, so long imports are no longer cut short by an
expiring access token. The key is mounted read only at runtime and is never
copied into the image.

Set these in `deploy/.env.prod`:

```
GOOGLE_DRIVE_SERVICE_ACCOUNT_HOST_FILE=/etc/cv-pipeline/google-drive-service-account.json
GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=/run/secrets/google-drive-service-account.json
GOOGLE_DRIVE_SHARED_DRIVE_ID=
```

`GOOGLE_DRIVE_SERVICE_ACCOUNT_HOST_FILE` is the host path and is only ever a
compose bind source; no host path appears in application source. It defaults to
`deploy/service-account.placeholder.json`, a committed non-credential, so the
mount always resolves on deployments that do not use Drive.
`GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` is the container path the API reads, and is
what switches service-account authentication on. `compose.prod.yml` mounts the
key at `/run/secrets/google-drive-service-account.json:ro` on the `api` service
only; the watcher does not import from Drive.

Store the key outside the repository, owned by root with mode `0400` or `0440`,
readable by the container user. Setting `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE`
without `GOOGLE_DRIVE_SERVICE_ACCOUNT_HOST_FILE` mounts the placeholder, and the
API rejects it at request time with an error naming the missing key fields.

`GOOGLE_DRIVE_SHARED_DRIVE_ID` is optional. When set, folder listings add
`corpora=drive` and `driveId=<id>`, which is what Google recommends for a service
account. When empty, listings keep today's `includeItemsFromAllDrives` behaviour.

`GOOGLE_DRIVE_ACCESS_TOKEN` / `GOOGLE_DRIVE_BEARER_TOKEN` and
`GOOGLE_DRIVE_API_KEY` still work and are read only when
`GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` is empty, so migration needs no flag day.

Credentials and the access token are cached in memory and keyed on the key
file's mtime and size: replacing the mounted file rotates the credential on the
next Drive call without a restart.

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
