#!/usr/bin/env bash
# 将镜像推到远程并 docker compose up（默认 SSH 流式 docker save | docker load，不占满本机 /tmp）
# 用法: REMOTE_USER=your-user REMOTE_HOST=<your-host-or-ip> ./scripts/deploy/publish-to-host.sh
# 可选: SAVE_VIA_TAR=1 改为先写本地 /tmp 再 scp（网络不稳时可重试 scp）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_USER="${REMOTE_USER:-gan}"
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_DIR="${REMOTE_DIR:-/home/${REMOTE_USER}/enterprise-rag-v2}"
TAR_NAME="${TAR_NAME:-enterprise-rag-v2-image.tar}"
# 长传镜像时防止 SSH 空闲被掐
SSH_OPTS=(-o ServerAliveInterval=30 -o ServerAliveCountMax=240)

cd "$ROOT"

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "请设置 REMOTE_HOST，例如：REMOTE_HOST=your-host ./scripts/deploy/publish-to-host.sh"
  exit 1
fi

if ! docker image inspect enterprise-rag-v2:latest &>/dev/null; then
  echo "请先构建: ./scripts/deploy/build-image.sh"
  exit 1
fi

echo "准备目录与编排文件 → ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}/runtime/logs' '${REMOTE_DIR}/runtime/data' '${REMOTE_DIR}/runtime/tmp'"
scp "${ROOT}/docker-compose.deploy.yml" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/docker-compose.yml"

if [[ "${SAVE_VIA_TAR:-}" == "1" ]]; then
  echo "模式: 本地 tar + scp（镜像大时请耐心等待）..."
  docker save enterprise-rag-v2:latest -o "/tmp/${TAR_NAME}"
  scp "${SSH_OPTS[@]}" "/tmp/${TAR_NAME}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<REMOTE
set -e
cd '${REMOTE_DIR}'
docker load -i '${TAR_NAME}'
rm -f '${TAR_NAME}'
docker compose up -d
docker compose ps
REMOTE
  rm -f "/tmp/${TAR_NAME}"
else
  echo "模式: SSH 管道流式传输（docker save | ssh docker load），无本地大 tar..."
  docker save enterprise-rag-v2:latest | ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "docker load"
  echo "启动 compose..."
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<REMOTE
set -e
cd '${REMOTE_DIR}'
docker compose up -d
docker compose ps
REMOTE
fi

echo "完成。访问: http://${REMOTE_HOST}:8000 （生产请配置 .env: DB_PASSWORD、JWT_SECRET 等）"
