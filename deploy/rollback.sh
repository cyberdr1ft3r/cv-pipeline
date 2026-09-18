#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PREVIOUS_FILE="$ROOT_DIR/deploy/.previous-version"
WATCHER_MODE_FILE="$ROOT_DIR/deploy/.deployed-watcher-mode"
if [ ! -s "$PREVIOUS_FILE" ]; then
  echo "no previous deployed version is recorded" >&2
  exit 2
fi

PREVIOUS_VERSION=$(tr -d '\r\n' < "$PREVIOUS_FILE")
if [ -s "$WATCHER_MODE_FILE" ]; then
  DEPLOY_WATCHER=$(tr -d '\r\n' < "$WATCHER_MODE_FILE")
else
  DEPLOY_WATCHER=0
fi
export DEPLOY_WATCHER
exec "$ROOT_DIR/deploy/deploy.sh" "$PREVIOUS_VERSION"
