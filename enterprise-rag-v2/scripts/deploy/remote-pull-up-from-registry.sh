#!/usr/bin/env bash
# 在目标机「只拉镜像 + compose up」，不向目标机同步业务源码。
# 前置：已将 web/worker 镜像推送到仓库（见 make release / scripts/release/release.sh PUSH=true）。
#
# 用法（在开发机执行，需 ssh 免密到目标机）：
#   cd enterprise-rag-v2
#   DOCKER_REGISTRY=ghcr.io/your-org/ IMAGE_TAG=v2.0.1 REMOTE_HOST=user@host.example ./scripts/deploy/remote-pull-up-from-registry.sh
#
# 可选：REMOTE_USER=deploy-user REMOTE_DIR=/srv/enterprise-rag-v2
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE_USER="${REMOTE_USER:-deploy-user}"
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_DIR="${REMOTE_DIR:-/srv/enterprise-rag-v2}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
SSH_OPTS=(-o ServerAliveInterval=30 -o ServerAliveCountMax=120)

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "请设置 REMOTE_HOST，例如：REMOTE_HOST=user@host.example $0"
  exit 1
fi
if [[ -z "${IMAGE_TAG}" ]]; then
  echo "请设置 IMAGE_TAG（与仓库中已推送的 tag 一致），例如：IMAGE_TAG=v2.0.1_202604181200_abcd1234"
  exit 1
fi
if [[ -z "${DOCKER_REGISTRY}" ]]; then
  echo "请设置 DOCKER_REGISTRY（须带尾部 /），例如：DOCKER_REGISTRY=ghcr.io/your-org/"
  exit 1
fi

cd "${ROOT}"

echo "==> 下发编排与脚本（仅 compose + startup，无 api/services 等源码）"
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "mkdir -p '${REMOTE_DIR}/runtime/logs' '${REMOTE_DIR}/runtime/data' '${REMOTE_DIR}/runtime/tmp' '${REMOTE_DIR}/shared/logs' '${REMOTE_DIR}/startup'"
scp "${SSH_OPTS[@]}" "${ROOT}/docker-compose.deploy.yml" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/docker-compose.yml"
for f in start-app.sh stop-app.sh show-version.sh apply_llm_env_fragment.py; do
  scp "${SSH_OPTS[@]}" "${ROOT}/scripts/deploy/${f}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/startup/${f}"
done
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "chmod +x '${REMOTE_DIR}/startup/start-app.sh' '${REMOTE_DIR}/startup/stop-app.sh' '${REMOTE_DIR}/startup/show-version.sh'"

echo "==> 合并远端 .env 中的 DOCKER_REGISTRY / IMAGE_TAG（不覆盖已有 INTERNAL_* / JWT 等）"
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_DIR}"
touch .env
for kv in 'DOCKER_REGISTRY=${DOCKER_REGISTRY}' 'IMAGE_TAG=${IMAGE_TAG}'; do
  key="\${kv%%=*}"
  if grep -q "^\${key}=" .env 2>/dev/null; then
    sed -i.bak "s|^\${key}=.*|\${kv}|" .env
  else
    echo "\${kv}" >> .env
  fi
done
REMOTE

echo "==> 远端拉取镜像并启动（需目标机能访问 ${DOCKER_REGISTRY}）"
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_DIR}"
export DOCKER_REGISTRY="${DOCKER_REGISTRY}"
export IMAGE_TAG="${IMAGE_TAG}"
docker compose pull
docker compose up -d --force-recreate
docker compose ps
REMOTE

echo "==> 健康检查 http://${REMOTE_HOST}:8000/health/live"
for i in $(seq 1 30); do
  if curl -fsS "http://${REMOTE_HOST}:8000/health/live" >/dev/null 2>&1; then
    echo "ok"
    exit 0
  fi
  sleep 2
done
echo "WARN: /health/live 未在预期时间内就绪，请 ssh 排查: cd ${REMOTE_DIR} && docker compose logs --tail=80 web"
exit 1
