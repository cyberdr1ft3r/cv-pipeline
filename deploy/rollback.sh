#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PREVIOUS_FILE="$ROOT_DIR/deploy/.previous-version"
if [ ! -s "$PREVIOUS_FILE" ]; then
  echo "no previous deployed version is recorded" >&2
  exit 2
fi

PREVIOUS_VERSION=$(tr -d '\r\n' < "$PREVIOUS_FILE")
exec "$ROOT_DIR/deploy/deploy.sh" "$PREVIOUS_VERSION"
