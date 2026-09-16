#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT_DIR/deploy/.env.prod"}
VERSION=${1:-${CV_PIPELINE_VERSION:-}}

if [ -z "$VERSION" ]; then
  echo "usage: deploy/deploy.sh <immutable-image-version>" >&2
  exit 2
fi
case "$VERSION" in
  *[!A-Za-z0-9_.-]*) echo "invalid image version" >&2; exit 2 ;;
esac
if [ ! -f "$ENV_FILE" ]; then
  echo "missing deployment environment file: $ENV_FILE" >&2
  exit 2
fi

CURRENT_FILE="$ROOT_DIR/deploy/.deployed-version"
PREVIOUS_FILE="$ROOT_DIR/deploy/.previous-version"
CURRENT_VERSION=""
if [ -s "$CURRENT_FILE" ]; then
  CURRENT_VERSION=$(tr -d '\r\n' < "$CURRENT_FILE")
fi

export CV_PIPELINE_VERSION="$VERSION"
compose() {
  docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/compose.prod.yml" "$@"
}

verify_required_services() {
  for service in postgres api watcher frontend proxy; do
    container_id=$(compose ps -q "$service")
    if [ -z "$container_id" ]; then
      echo "required service has no container: $service" >&2
      return 1
    fi

    state=$(docker inspect --format '{{.State.Status}} {{.State.Restarting}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")
    set -- $state
    status=$1
    restarting=$2
    health=$3
    if [ "$status" != "running" ] || [ "$restarting" != "false" ]; then
      echo "required service is not stably running: $service ($state)" >&2
      return 1
    fi
    if [ "$health" != "none" ] && [ "$health" != "healthy" ]; then
      echo "required service is not healthy: $service ($state)" >&2
      return 1
    fi
  done
}

compose config --quiet
compose pull
compose up -d --remove-orphans
PROXY_ADDRESS=$(compose port proxy 80 | tail -n 1)
if ! CV_PIPELINE_HEALTH_URL="http://$PROXY_ADDRESS" "$ROOT_DIR/deploy/healthcheck.sh" || ! verify_required_services; then
  echo "deployment failed health checks" >&2
  if [ -n "$CURRENT_VERSION" ]; then
    echo "restoring previously deployed image version" >&2
    export CV_PIPELINE_VERSION="$CURRENT_VERSION"
    compose pull
    compose up -d --remove-orphans
  fi
  exit 1
fi

if [ -n "$CURRENT_VERSION" ]; then
  printf '%s\n' "$CURRENT_VERSION" > "$PREVIOUS_FILE"
fi
printf '%s\n' "$VERSION" > "$CURRENT_FILE"
