#!/usr/bin/env bash
# =============================================================
# Rollback Production Deployment
#
# 用途：从失败的部署快速回滚到上一个稳定版本
# 使用备份恢复配置和之前的镜像
#
# 用法：
#   bash scripts/deploy/rollback-production.sh
# =============================================================
set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROD_HOST="${PROD_HOST:?Set PROD_HOST=user@host}"
PROD_DIR="${PROD_DIR:?Set PROD_DIR to the project directory on the production host}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.deploy.yml}"

echo "=========================================================="
echo "Initiating Production Rollback"
echo "=========================================================="
echo "Target: $PROD_HOST"
echo ""

# 获取确认（如果本地运行）
if [ "$0" != "-bash" ] && [ -t 0 ]; then
    read -p "Are you sure you want to rollback production? (type 'ROLLBACK' to confirm): " -r
    echo
    if [[ ! $REPLY = "ROLLBACK" ]]; then
        echo "Cancelled."
        exit 1
    fi
fi

# SSH 到生产环境执行回滚
ssh -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$PROD_HOST" << 'SSHEOF'
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "${PROD_DIR}"

# 查找最新的备份
LATEST_BACKUP=$(ls -t backups/.env.* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${RED}✗ No backup found to restore${NC}"
    echo ""
    echo "Backup directory: ${PROD_DIR}/backups/"
    echo "Expected files: .env.<timestamp>"
    echo ""
    echo "Possible causes:"
    echo "  1. This is the first deployment (no prior backup exists)"
    echo "  2. The backups directory was manually cleaned"
    echo "  3. The previous deployment step (Step 3/6) failed before creating backup"
    echo ""
    echo -e "${YELLOW}Suggestion:${NC} If this is a re-deployment, the current .env may still be valid."
    echo "Run 'docker compose up -d' manually on the production host to restart with current config."
    exit 1

echo -e "${BLUE}Restoring from backup:${NC} $LATEST_BACKUP"

# 停止当前容器
echo "Stopping current containers..."
docker compose down || true

# 恢复备份
echo "Restoring configuration from backup..."
cp "$LATEST_BACKUP" .env

# 清理失败的镜像
echo "Cleaning up failed images..."
docker image prune -f || true

# 启动之前的版本
echo "Starting previous version..."
docker compose up -d || {
    echo -e "${RED}✗ Failed to start containers from backup${NC}"
    exit 1
}

# 等待服务启动
sleep 5

# 验证服务状态
if curl -s http://localhost:8000/health >/dev/null; then
    echo -e "${GREEN}✓ Rollback successful${NC}"

    # 显示当前运行的版本
    CURRENT_VERSION=$(docker compose ps 2>/dev/null | grep web | awk '{print $2}' | cut -d: -f2 | head -1 || echo "unknown")
    echo "Current version: $CURRENT_VERSION"
else
    echo -e "${YELLOW}⚠ Rollback completed, but services may not be healthy${NC}"
    echo "Please verify manually and investigate the failure"
    exit 1
fi
SSHEOF

echo ""
echo "=========================================================="
echo -e "${GREEN}✓ Production rollback completed${NC}"
echo "=========================================================="
echo ""
echo "Actions to take:"
echo "1. Verify production is healthy:"
echo "   curl http://${PROD_HOST#*@}:8000/health"
echo ""
echo "2. Check logs for issues:"
echo "   ssh ${PROD_HOST} 'cd "${REMOTE_DIR}" && docker compose logs -f'"
echo ""
echo "3. Investigate root cause of deployment failure"
echo ""
echo "4. Once issue is resolved, retry deployment with fixes"
echo ""
