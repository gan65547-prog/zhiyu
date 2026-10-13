#!/usr/bin/env bash
set -euo pipefail

# 启动应用（db + redis + web + worker）
# 支持在远端 startup 目录或本地 scripts/deploy 目录执行
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

echo "[start-app] using compose: ${COMPOSE_FILE}"
cd "${ROOT_DIR}"
docker compose -f "${COMPOSE_FILE}" up -d
docker compose -f "${COMPOSE_FILE}" ps
echo "[start-app] done"
