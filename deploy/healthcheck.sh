#!/usr/bin/env sh
set -eu

BASE_URL=${CV_PIPELINE_HEALTH_URL:-http://127.0.0.1:8080}
ATTEMPTS=${HEALTHCHECK_ATTEMPTS:-30}

i=1
while [ "$i" -le "$ATTEMPTS" ]; do
  if curl --fail --silent --show-error "$BASE_URL/healthz" >/dev/null \
    && curl --fail --silent --show-error "$BASE_URL/api/v1/health" >/dev/null \
    && curl --fail --silent --show-error "$BASE_URL/" >/dev/null; then
    echo "deployment health checks passed"
    exit 0
  fi
  sleep 2
  i=$((i + 1))
done

echo "deployment health checks failed" >&2
exit 1
