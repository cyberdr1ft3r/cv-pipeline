#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT_DIR/deploy/.env.prod"}
VERSION=${1:-${CV_PIPELINE_VERSION:-}}
DEPLOY_WATCHER=${DEPLOY_WATCHER:-0}

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
case "$DEPLOY_WATCHER" in
  0|1) ;;
  *) echo "DEPLOY_WATCHER must be exactly 0 or 1" >&2; exit 2 ;;
esac

CURRENT_FILE="$ROOT_DIR/deploy/.deployed-version"
PREVIOUS_FILE="$ROOT_DIR/deploy/.previous-version"
WATCHER_MODE_FILE="$ROOT_DIR/deploy/.deployed-watcher-mode"
CURRENT_VERSION=""
if [ -s "$CURRENT_FILE" ]; then
  CURRENT_VERSION=$(tr -d '\r\n' < "$CURRENT_FILE")
fi

export CV_PIPELINE_VERSION="$VERSION"
compose_base() {
  docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/compose.prod.yml" "$@"
}

compose() {
  if [ "$DEPLOY_WATCHER" = "1" ]; then
    compose_base --profile watcher "$@"
  else
    compose_base "$@"
  fi
}

DEPLOY_SERVICES="postgres api frontend proxy"
REQUIRED_SERVICES="$DEPLOY_SERVICES"
if [ "$DEPLOY_WATCHER" = "1" ]; then
  DEPLOY_SERVICES="postgres api watcher frontend proxy"
  REQUIRED_SERVICES="$DEPLOY_SERVICES"
fi

verify_required_services() {
  for service in $REQUIRED_SERVICES; do
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

if [ "$DEPLOY_WATCHER" = "0" ]; then
  echo "watcher deployment disabled; stopping any existing watcher container"
  compose_base --profile watcher stop watcher
fi

compose config --quiet
compose pull $DEPLOY_SERVICES
compose up -d --remove-orphans $DEPLOY_SERVICES
PROXY_ADDRESS=$(compose port proxy 80 | tail -n 1)
if ! CV_PIPELINE_HEALTH_URL="http://$PROXY_ADDRESS" "$ROOT_DIR/deploy/healthcheck.sh" || ! verify_required_services; then
  echo "deployment failed health checks" >&2
  if [ -n "$CURRENT_VERSION" ]; then
    echo "restoring previously deployed image version" >&2
    export CV_PIPELINE_VERSION="$CURRENT_VERSION"
    compose pull $DEPLOY_SERVICES
    compose up -d --remove-orphans $DEPLOY_SERVICES
  fi
  exit 1
fi

if [ -n "$CURRENT_VERSION" ]; then
  printf '%s\n' "$CURRENT_VERSION" > "$PREVIOUS_FILE"
fi
printf '%s\n' "$VERSION" > "$CURRENT_FILE"
printf '%s\n' "$DEPLOY_WATCHER" > "$WATCHER_MODE_FILE"
