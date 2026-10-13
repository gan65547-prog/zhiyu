#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${SCRIPT_DIR}/../docker-compose.yml" ]]; then
  ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
ENV_FILE="${ROOT_DIR}/.env"

echo "== .env release fields =="
if [[ -f "${ENV_FILE}" ]]; then
  grep -E '^(APP_VERSION|IMAGE_TAG|RELEASED_AT|RELEASE_GIT_TAG|RELEASE_GIT_SHA)=' "${ENV_FILE}" || true
else
  echo "no .env found at ${ENV_FILE}"
fi

echo
echo "== compose images (web, worker, qdrant) =="
if [[ -f "${COMPOSE_FILE}" ]]; then
  docker compose -f "${COMPOSE_FILE}" images web worker qdrant || true
else
  echo "no compose file found at ${COMPOSE_FILE}"
fi

echo
echo "== container images (web, worker, qdrant) =="
docker inspect enterprise-rag-v2-web-1 --format 'web {{.Config.Image}}' 2>/dev/null || echo "web container not found"
docker inspect enterprise-rag-v2-worker-1 --format 'worker {{.Config.Image}}' 2>/dev/null || echo "worker container not found"
docker inspect enterprise-rag-v2-qdrant-1 --format 'qdrant {{.Config.Image}}' 2>/dev/null || echo "qdrant container not found"
