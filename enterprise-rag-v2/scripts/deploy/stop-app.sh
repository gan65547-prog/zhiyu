#!/usr/bin/env bash
set -euo pipefail

# 停止应用（保留数据卷）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${SCRIPT_DIR}/../docker-compose.yml" ]]; then
  ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "未找到 ${COMPOSE_FILE}"
  exit 1
fi

echo "[stop-app] using compose: ${COMPOSE_FILE}"
cd "${ROOT_DIR}"
docker compose -f "${COMPOSE_FILE}" down
docker compose -f "${COMPOSE_FILE}" ps
echo "[stop-app] done"
