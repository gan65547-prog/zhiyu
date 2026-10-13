#!/usr/bin/env bash
# =============================================================
# Create Staging Release Tag
#
# 用途：为新版本创建 staging 标签并推送到 git 仓库
# 标签格式：staging-v{major}.{minor}.{patch}_{YYYYMMDDHHMM}_{git_sha8}
#
# 用法：
#   bash scripts/release/create-staging-tag.sh [version]
#   bash scripts/release/create-staging-tag.sh 2.0.21
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

cd "$PROJECT_ROOT/enterprise-rag-v2"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 参数
VERSION="${1:-}"

if [ -z "$VERSION" ]; then
    echo -e "${RED}Error: Version not provided${NC}"
    echo "Usage: bash scripts/release/create-staging-tag.sh <version>"
    echo "Example: bash scripts/release/create-staging-tag.sh 2.0.21"
    exit 1
fi

# 验证版本格式
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid version format${NC}"
    echo "Expected format: MAJOR.MINOR.PATCH (e.g., 2.0.21)"
    exit 1
fi

# 生成时间戳和 git SHA
TIMESTAMP=$(date +%Y%m%d%H%M)
GIT_SHA=$(git rev-parse --short=8 HEAD)
GIT_FULL_SHA=$(git rev-parse HEAD)

# 生成 staging 标签
STAGING_TAG="staging-v${VERSION}_${TIMESTAMP}_${GIT_SHA}"

echo "=========================================================="
echo "Creating Staging Release Tag"
echo "=========================================================="
echo "Version: $VERSION"
echo "Timestamp: $TIMESTAMP"
echo "Git SHA: $GIT_SHA (full: $GIT_FULL_SHA)"
echo "Staging Tag: $STAGING_TAG"
echo ""

# 检查标签是否已存在
if git rev-parse "$STAGING_TAG" >/dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Tag '$STAGING_TAG' already exists${NC}"
    read -p "Do you want to overwrite it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 1
    fi
    git tag -d "$STAGING_TAG"
fi

# 创建注解标签
git tag -a "$STAGING_TAG" -m "Staging release v$VERSION

Commit: $GIT_FULL_SHA
Deployed to the host configured for this release
Status: Pending validation

Release created at: $(date)
" || {
    echo -e "${RED}Failed to create tag${NC}"
    exit 1
}

echo -e "${GREEN}✓ Tag created:${NC} $STAGING_TAG"

# 推送标签到远程仓库
echo ""
echo "Pushing tag to remote repository..."

if git push origin "$STAGING_TAG"; then
    echo -e "${GREEN}✓ Tag pushed to remote${NC}"
else
    echo -e "${YELLOW}Warning: Failed to push tag to remote${NC}"
    echo "You can manually push with: git push origin $STAGING_TAG"
fi

# 输出下一步说明
echo ""
echo "=========================================================="
echo -e "${GREEN}✓ Staging tag created successfully${NC}"
echo "=========================================================="
echo ""
echo "Next steps:"
echo "1. Deploy to staging:"
echo "   bash scripts/deploy/deploy-to-staging.sh $STAGING_TAG"
echo ""
echo "2. Validate staging deployment:"
echo "   bash scripts/test/validate-staging-deployment.sh"
echo ""
echo "3. If validation passes, promote to production:"
echo "   bash scripts/deploy/promote-staging-to-production.sh $STAGING_TAG"
echo ""
