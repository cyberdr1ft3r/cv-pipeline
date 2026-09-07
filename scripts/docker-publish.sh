#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_USER="${1:?Usage: $0 <dockerhub-user> [tag] [frontend-api-url]}"
TAG="${2:-latest}"
FRONTEND_API_URL="${3:-/api/v1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

API_IMAGE="${DOCKERHUB_USER}/cv-pipeline-api:${TAG}"
FRONTEND_IMAGE="${DOCKERHUB_USER}/cv-pipeline-frontend:${TAG}"

echo "Building API: ${API_IMAGE}"
docker build -f "${ROOT}/service/Dockerfile" -t "${API_IMAGE}" "${ROOT}"

echo "Building frontend: ${FRONTEND_IMAGE} (NEXT_PUBLIC_API_URL=${FRONTEND_API_URL})"
docker build \
  -f "${ROOT}/frontend_enterprise/Dockerfile" \
  --build-arg "NEXT_PUBLIC_API_URL=${FRONTEND_API_URL}" \
  -t "${FRONTEND_IMAGE}" \
  "${ROOT}/frontend_enterprise"

docker push "${API_IMAGE}"
docker push "${FRONTEND_IMAGE}"

echo ""
echo "Published:"
echo "  ${API_IMAGE}"
echo "  ${FRONTEND_IMAGE}"
