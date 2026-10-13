#!/usr/bin/env bash
# 将源码同步到远程 Linux 主机并在其上 docker build + compose up。
# 适用于：本机构建时出现 pip DNS 失败（Name or service not known），或 macOS Docker Desktop 网络限制。
# 用法: ./scripts/deploy/deploy-on-remote.sh
# 需: ssh 免密登录 REMOTE_HOST；远端已安装 docker 与 docker compose plugin
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_USER="${REMOTE_USER:-gan}"
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_DIR="${REMOTE_DIR:-/home/${REMOTE_USER}/erag-deploy}"

cd "$ROOT"

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "请设置 REMOTE_HOST，例如：REMOTE_HOST=your-host ./scripts/deploy/deploy-on-remote.sh"
  exit 1
fi

echo "同步源码到 ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR} ..."
# 先创建主目录，确保用户有权限
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}'"
# 然后创建子目录
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}/runtime/logs' '${REMOTE_DIR}/runtime/data' '${REMOTE_DIR}/runtime/tmp'"

rsync -az --delete \
  --exclude '.git/' \
  --exclude '.DS_Store' \
  --exclude '.venv-ci/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.db' \
  --exclude 'dump.rdb' \
  --exclude 'frontend/node_modules/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude 'runtime/logs/' \
  --exclude '*.tar' \
  "${ROOT}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

scp "${ROOT}/docker-compose.deploy.yml" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/docker-compose.yml"

echo "在远端构建镜像（DOCKER_BUILDKIT=0 兼容仅 docker.io、无 buildx 的环境）..."
ssh "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_DIR}"
export DOCKER_BUILDKIT=0
docker build \
  --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL:-}" \
  --build-arg "PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL:-}" \
  --build-arg "NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY:-}" \
  -t enterprise-rag-v2:latest \
  .
echo "启动基础服务..."
docker compose -f docker-compose.yml up -d db redis qdrant
echo "执行数据库迁移..."
docker compose -f docker-compose.yml run --rm web alembic upgrade head
echo "启动 web 服务..."
docker compose -f docker-compose.yml up -d web
docker compose -f docker-compose.yml ps
REMOTE

echo "完成。访问: http://${REMOTE_HOST}:8000"
