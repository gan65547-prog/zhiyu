#!/usr/bin/env bash
# =============================================================
# Promote Staging to Production
#
# 用途：将经过验证的 staging 版本推送到生产环境
# 包括：创建 production tag、备份、部署、验证、自动回滚
#
# 用法：
#   bash scripts/deploy/promote-staging-to-production.sh <staging-tag>
#   bash scripts/deploy/promote-staging-to-production.sh staging-v2.0.21_202604211234_abc12345
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

die() {
    echo -e "${RED}Error: $*${NC}" >&2
    exit 1
}

# 参数
STAGING_TAG="${1:-}"
PROD_HOST="${PROD_HOST:-}"
PROD_DIR="${PROD_DIR:-}"
PROD_PORT="${PROD_PORT:-8000}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.deploy.yml}"

if [ -z "$STAGING_TAG" ]; then
    echo -e "${RED}Error: Staging tag not provided${NC}"
    echo "Usage: bash scripts/deploy/promote-staging-to-production.sh <staging-tag>"
    echo "Example: bash scripts/deploy/promote-staging-to-production.sh staging-v2.0.21_202604211234_abc12345"
    exit 1
fi
if [ -z "$PROD_HOST" ]; then
    echo -e "${RED}Error: PROD_HOST is required; refusing an implicit production target${NC}"
    exit 1
fi
if [ -z "$PROD_DIR" ]; then
    echo -e "${RED}Error: PROD_DIR is required; refusing an implicit production path${NC}"
    exit 1
fi

# 验证标签格式
if [[ ! "$STAGING_TAG" =~ ^staging-v([0-9]+\.[0-9]+\.[0-9]+)_([0-9]+)_([a-f0-9]{8})$ ]]; then
    echo -e "${RED}Error: Invalid staging tag format${NC}"
    echo "Expected format: staging-v{major}.{minor}.{patch}_{YYYYMMDDHHMM}_{git_sha8}"
    exit 1
fi

VERSION="${BASH_REMATCH[1]}"
TIMESTAMP="${BASH_REMATCH[2]}"
GIT_SHA="${BASH_REMATCH[3]}"
PROD_TAG="release-v${VERSION}_${TIMESTAMP}_${GIT_SHA}"

echo "=========================================================="
echo "Promoting Staging to Production"
echo "=========================================================="
echo "Staging tag: $STAGING_TAG"
echo "Production tag: $PROD_TAG"
echo "Version: $VERSION"
echo "Target: $PROD_HOST"
echo ""

# 获取用户确认
read -p "Are you sure you want to deploy to production? (type 'yes' to continue): " -r
echo
if [[ ! $REPLY = "yes" ]]; then
    echo "Cancelled."
    exit 1
fi

# Step 1: 验证 git tag 存在
echo -e "${BLUE}[Step 1/6]${NC} Verifying staging tag..."
cd "$PROJECT_ROOT"

if ! git rev-parse "$STAGING_TAG" >/dev/null 2>&1; then
    echo -e "${RED}✗ Staging tag not found: $STAGING_TAG${NC}"
    exit 1
fi

GIT_FULL_SHA=$(git rev-parse "${STAGING_TAG}^{commit}")
echo -e "${GREEN}✓ Staging tag verified${NC}"
echo "  Git commit: $GIT_FULL_SHA"

# Fail closed before any production tag, backup, image transfer, or remote
# mutation. The release verifier also checks candidate ancestry and required
# backup/rollback evidence.
WEB_IMAGE="${WEB_IMAGE:-}"
WORKER_IMAGE="${WORKER_IMAGE:-}"
DB_PASSWORD="${PROD_DB_PASSWORD:-${DB_PASSWORD:-}}"
JWT_SECRET="${PROD_JWT_SECRET:-${JWT_SECRET:-}}"
CSRF_SECRET="${PROD_CSRF_SECRET:-${CSRF_SECRET:-}}"
OPENAI_API_KEY="${PROD_OPENAI_API_KEY:-${OPENAI_API_KEY:-}}"
INTERNAL_API_KEYS="${PROD_INTERNAL_API_KEYS:-${INTERNAL_API_KEYS:-}}"
INTERNAL_IP_WHITELIST="${PROD_INTERNAL_IP_WHITELIST:-${INTERNAL_IP_WHITELIST:-}}"
if [[ ! "$WEB_IMAGE" =~ ^[^/]+/[^@]+@sha256:[0-9a-f]{64}$ || ! "$WORKER_IMAGE" =~ ^[^/]+/[^@]+@sha256:[0-9a-f]{64}$ ]]; then
    echo -e "${RED}Error: WEB_IMAGE and WORKER_IMAGE must be immutable registry digests${NC}"
    exit 1
fi
for required in DB_PASSWORD JWT_SECRET CSRF_SECRET OPENAI_API_KEY INTERNAL_API_KEYS INTERNAL_IP_WHITELIST; do
    if [[ -z "${!required}" || "${!required}" == *change-this* ]]; then
        echo -e "${RED}Error: production ${required} is missing or a placeholder${NC}"
        exit 1
    fi
done
export WEB_IMAGE WORKER_IMAGE DB_PASSWORD JWT_SECRET CSRF_SECRET OPENAI_API_KEY
export INTERNAL_API_KEYS INTERNAL_IP_WHITELIST RELEASE_GIT_SHA="$GIT_FULL_SHA"
bash "${PROJECT_ROOT}/scripts/release/verify-candidate.sh"
if [[ "${CONFIRM_PRODUCTION:-}" != "yes" ]]; then
    echo -e "${YELLOW}Preflight passed. Set CONFIRM_PRODUCTION=yes to authorize production writes.${NC}"
    exit 1
fi

# Step 2: 保留 production tag 创建到部署成功之后
echo ""
echo -e "${BLUE}[Step 2/6]${NC} Creating production tag..."
cd "$PROJECT_ROOT"
echo "Production tag will be created only after readiness passes."

# Step 3: 备份当前 production 配置
echo ""
echo -e "${BLUE}[Step 3/6]${NC} Backing up current production configuration..."

ssh -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$PROD_HOST" << SSHEOF
    set -euo pipefail

    cd "${PROD_DIR}"

    [[ -f .env ]] || { echo "ERROR: production .env is missing" >&2; exit 1; }

    # 创建备份目录
    mkdir -p backups

    # 备份当前 .env 和 compose 文件
    BACKUP_TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
    cp .env "backups/.env.\$BACKUP_TIMESTAMP" || true
    cp ${COMPOSE_FILE} "backups/${COMPOSE_FILE}.\$BACKUP_TIMESTAMP" || true
    if docker compose -f ${COMPOSE_FILE} ps db --status running --format '{{.Name}}' | grep -q .; then
        docker compose -f ${COMPOSE_FILE} exec -T db pg_dump -U postgres -d ragdb -Fc > "backups/ragdb.\$BACKUP_TIMESTAMP.dump"
    fi

    echo "Production backup created: \$BACKUP_TIMESTAMP"
SSHEOF

echo -e "${GREEN}✓ Production configuration backed up${NC}"

# Step 4: 使用 immutable registry digest
echo ""
echo -e "${BLUE}[Step 4/6]${NC} Production will pull the pinned registry digests"

# Step 5: 启动 production 容器
echo ""
echo -e "${BLUE}[Step 5/6]${NC} Starting production containers..."

PROD_BASE_URL="${PROD_BASE_URL:-http://${PROD_HOST#*@}:${PROD_PORT}}"
PROD_INTERNAL_API_KEY="${PROD_INTERNAL_API_KEY:-}"
PROD_INTERNAL_IP_WHITELIST="${PROD_INTERNAL_IP_WHITELIST:-}"
[[ -n "$PROD_INTERNAL_API_KEY" && -n "$PROD_INTERNAL_IP_WHITELIST" ]] || die "production internal API key and IP whitelist are required"

ssh -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$PROD_HOST" << SSHEOF
    set -euo pipefail

    cd "${PROD_DIR}"

    # 更新环境变量（覆盖 .env 中的预发布配置）
    export WEB_IMAGE="${WEB_IMAGE}"
    export WORKER_IMAGE="${WORKER_IMAGE}"
    export DB_PASSWORD="${DB_PASSWORD}"
    export JWT_SECRET="${JWT_SECRET}"
    export CSRF_SECRET="${CSRF_SECRET}"
    export OPENAI_API_KEY="${OPENAI_API_KEY}"
    export IMAGE_TAG="${PROD_TAG}"
    export APP_VERSION="v${VERSION}"
    export RELEASED_AT="\$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    export RELEASE_GIT_TAG="${PROD_TAG}"
    export RELEASE_GIT_SHA="${RELEASE_GIT_SHA}"

    # 生产环境关键配置（强制覆盖预发布值）
    export ENVIRONMENT=production
    export BASE_URL="${PROD_BASE_URL}"
    export INTERNAL_API_KEYS='["${PROD_INTERNAL_API_KEY}"]'
    export INTERNAL_IP_WHITELIST='["${PROD_INTERNAL_IP_WHITELIST}"]'
    export INTERNAL_API_KEYS="${INTERNAL_API_KEYS}"
    export INTERNAL_IP_WHITELIST="${INTERNAL_IP_WHITELIST}"
    docker pull "\${WEB_IMAGE}"
    docker pull "\${WORKER_IMAGE}"
    echo "  - OPENAI_API_KEY=<configured>"

    # 停止旧容器
    docker compose -f ${COMPOSE_FILE} down || true

    # 启动新容器
    docker compose -f ${COMPOSE_FILE} up -d

    echo "Production containers started with:"
    echo "  - ENVIRONMENT=\${ENVIRONMENT}"
    echo "  - BASE_URL=\${BASE_URL}"
    echo "  - secrets supplied by deployment environment"
SSHEOF

echo -e "${GREEN}✓ Production containers started${NC}"

# Step 6: 验证生产环境
echo ""
echo -e "${BLUE}[Step 6/6]${NC} Verifying production deployment..."

PROD_URL="http://${PROD_HOST#*@}:${PROD_PORT}"
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=2

for i in $(seq 1 $HEALTH_CHECK_RETRIES); do
    echo -n "."

    if curl -s -f "${PROD_URL}/health/ready" >/dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Production services healthy${NC}"
        break
    fi

    if [ $i -eq $HEALTH_CHECK_RETRIES ]; then
        echo ""
        echo -e "${RED}✗ Production services unhealthy after $((HEALTH_CHECK_RETRIES * HEALTH_CHECK_INTERVAL)) seconds${NC}"
        echo ""
        echo "Attempting automatic rollback..."

        ssh -o StrictHostKeyChecking=no \
            -o UserKnownHostsFile=/dev/null \
            "$PROD_HOST" "bash ${PROD_DIR}/scripts/deploy/rollback-production.sh" || true

        exit 1
    fi

    sleep $HEALTH_CHECK_INTERVAL
done

# Tag only after the remote deployment is healthy. A failed promotion leaves
# the repository without a production tag and therefore cannot look released.
git tag -a "$PROD_TAG" -m "Production release v$VERSION

Promoted from: $STAGING_TAG
Commit: $GIT_FULL_SHA
Web image: $WEB_IMAGE
Worker image: $WORKER_IMAGE
"

# 推送 production tag 到远程
echo ""
echo "Pushing production tag to git..."
if git push origin "$PROD_TAG"; then
    echo -e "${GREEN}✓ Production tag pushed${NC}"
else
    echo -e "${YELLOW}Warning: Could not push production tag${NC}"
fi

# 完成
echo ""
echo "=========================================================="
echo -e "${GREEN}✓ Production deployment successful${NC}"
echo "=========================================================="
echo ""
echo "Production environment details:"
echo "  URL: ${PROD_URL}"
echo "  Version: v$VERSION"
echo "  Staging tag: $STAGING_TAG"
echo "  Production tag: $PROD_TAG"
echo ""
echo "Next steps:"
echo "1. Monitor production logs and metrics"
echo "2. Notify stakeholders of the deployment"
echo "3. Update DEPLOYMENT_LOG.md with release details"
echo "4. If issues arise, contact the on-call engineer"
echo ""
