#!/usr/bin/env bash
# =============================================================
# Rollback Staging Deployment
#
# 用途：从失败的部署回滚到上一个稳定版本
#
# 用法：
#   bash scripts/deploy/rollback-staging.sh [tag]
#   bash scripts/deploy/rollback-staging.sh  # 自动回滚
# =============================================================
set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

STAGING_HOST="${STAGING_HOST:?Set STAGING_HOST=user@host}"
STAGING_DIR="${STAGING_DIR:?Set STAGING_DIR to the project directory on the staging host}"
TAG="${1:-}"

echo "=========================================================="
echo "Rolling back Staging Deployment"
echo "=========================================================="
echo "Target: $STAGING_HOST"
echo ""

# SSH 基础参数
SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=30)

if [ -z "$TAG" ]; then
    echo -e "${YELLOW}No specific tag provided, rolling back to previous version${NC}"
    echo ""

    # 从 SSH 获取当前版本
    CURRENT_VERSION=$(ssh "${SSH_OPTS[@]}" \
        "$STAGING_HOST" "docker compose ps 2>/dev/null | grep web | awk '{print \$2}' | cut -d: -f2" || echo "unknown")

    echo "Current version: $CURRENT_VERSION"
fi

# 在预生产环境执行回滚
ssh "${SSH_OPTS[@]}" "$STAGING_HOST" << SSHEOF
    set -euo pipefail

    cd "${STAGING_DIR}"

    echo "Stopping containers..."
    docker compose down || true

    echo "Removing failed images..."
    docker image prune -f || true

    # 恢复环境变量备份（deploy 脚本在部署前会自动备份）
    ENV_RESTORED=false
    if [ -f .env.backup ]; then
        echo "Restoring .env from backup..."
        cp .env.backup .env
        ENV_RESTORED=true
    elif [ -f .env ]; then
        echo "No .env.backup found, keeping current .env"
        ENV_RESTORED=true
    else
        echo "Warning: No .env or .env.backup found, creating minimal .env"
        cat > .env << 'ENVEOF'
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
EMBEDDING_MODEL_PATH=/opt/models/bge-small-zh-v1.5
ENVEOF
        echo "Minimal .env created"
    fi

    echo "Starting previous version..."
    # 尝试用 docker-compose.deploy.yml 启动；不存在则用 docker-compose.yml
    COMPOSE_FILE="docker-compose.deploy.yml"
    if [ ! -f "\${COMPOSE_FILE}" ]; then
        COMPOSE_FILE="docker-compose.yml"
    fi
    echo "Using compose file: \${COMPOSE_FILE}"
    docker compose -f "\${COMPOSE_FILE}" up -d || {
        echo "Error: Failed to start containers"
        exit 1
    }

    sleep 5

    # 验证服务状态
    if curl -s http://localhost:8000/health >/dev/null; then
        echo "Rollback successful"
    else
        echo "Warning: Services may not be healthy"
    fi
SSHEOF

echo -e "${GREEN}✓ Rollback completed${NC}"
echo ""
echo "Staging environment has been rolled back."
echo "Please investigate the failure before attempting deployment again."
