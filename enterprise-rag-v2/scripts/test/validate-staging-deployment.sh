#!/usr/bin/env bash
# =============================================================
# Validate Staging Deployment
#
# 用途：验证预生产环境中的所有 API 端点和核心业务流程
# 包括：健康检查、API 测试、集成流程验证
#
# 用法：
#   bash scripts/test/validate-staging-deployment.sh
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

# 配置
STAGING_HOST="${STAGING_HOST:-${STAGING_HOST:?Set STAGING_HOST=user@host}}"
STAGING_PORT="${STAGING_PORT:-8000}"
STAGING_URL="http://${STAGING_HOST#*@}:${STAGING_PORT}"
API_KEY="${INTERNAL_API_KEY:-test-staging-key}"
MIGRATION_VALIDATION_COMMAND="${MIGRATION_VALIDATION_COMMAND:-}"

# 测试结果
PASSED=0
FAILED=0

test_case() {
    local name="$1"
    local test_fn="$2"

    echo ""
    echo -e "${BLUE}Testing:${NC} $name"

    if $test_fn; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓ PASSED${NC}"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗ FAILED${NC}"
    fi
}

# Test 1: Health check
test_health_check() {
    local health_url="$STAGING_URL/health"
    local response
    response=$(curl -fsS --max-time 15 "$health_url") || { echo "health request failed"; return 1; }
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status") == "healthy"; assert all(c.get("status") == "healthy" for c in d.get("components", []))' <<<"$response" || {
        echo "Health response is not fully healthy"
        return 1
    }
}

# Test 2: Readiness probe
test_readiness() {
    local ready_url="$STAGING_URL/health/ready"
    curl -fsS --max-time 15 "$ready_url" >/dev/null || { echo "readiness request failed"; return 1; }
}

# Test 3: API root endpoint
test_api_root() {
    local response=$(curl -s -w "\n%{http_code}" "$STAGING_URL/")
    local http_code=$(echo "$response" | tail -n 1)

    if [ "$http_code" = "200" ]; then
        return 0
    else
        echo "HTTP $http_code"
        return 1
    fi
}

# Test 4: OpenAPI schema
test_openapi_schema() {
    local schema_url="$STAGING_URL/api/openapi.json"
    local response=$(curl -s -w "\n%{http_code}" "$schema_url")
    local http_code=$(echo "$response" | tail -n 1)

    if [ "$http_code" = "200" ]; then
        return 0
    else
        echo "HTTP $http_code"
        return 1
    fi
}

# Test 5: Database connectivity (via health endpoint)
test_database_connectivity() {
    # Since there's no dedicated /internal/admin/health/database endpoint,
    # we verify database is accessible through the main health endpoint
    local response=$(curl -s "$STAGING_URL/health")

    if echo "$response" | grep -q '"name":"database"' && echo "$response" | grep -q '"status":"healthy"'; then
        return 0
    else
        echo "Database not healthy in health response"
        return 1
    fi
}

# Test 6: Redis connectivity
test_redis_connectivity() {
    local response
    response=$(curl -fsS --max-time 15 "$STAGING_URL/health") || { echo "health request failed"; return 1; }
    python3 -c 'import json,sys; d=json.load(sys.stdin); assert any(c.get("name") == "redis" and c.get("status") == "healthy" for c in d.get("components", []))' <<<"$response" || {
        echo "Redis is not healthy in health response"
        return 1
    }
}

# Test 7: Metrics endpoint
test_metrics_endpoint() {
    local metrics_url="$STAGING_URL/metrics"
    local http_code
    http_code=$(curl -sS --max-time 15 -o /dev/null -w "%{http_code}" "$metrics_url" \
        -H "Authorization: Bearer $API_KEY")

    if [ "$http_code" = "200" ]; then
        return 0
    else
        echo "HTTP $http_code"
        return 1
    fi
}

# Test 8: Database migrations applied
test_migrations_applied() {
    if [ -z "$MIGRATION_VALIDATION_COMMAND" ]; then
        echo "MIGRATION_VALIDATION_COMMAND is required; refusing to treat liveness as migration evidence"
        return 1
    fi
    bash -lc "$MIGRATION_VALIDATION_COMMAND"
}

# Main
main() {
    echo "=========================================================="
    echo "Validating Staging Deployment"
    echo "=========================================================="
    echo "Target URL: $STAGING_URL"
    echo ""

    # 健康检查
    echo -e "${BLUE}=== Health Checks ===${NC}"
    test_case "Health check endpoint" test_health_check
    test_case "Readiness probe" test_readiness
    test_case "API root endpoint" test_api_root

    # API 端点
    echo ""
    echo -e "${BLUE}=== API Endpoints ===${NC}"
    test_case "OpenAPI schema" test_openapi_schema
    test_case "Metrics endpoint" test_metrics_endpoint

    # 依赖关系
    echo ""
    echo -e "${BLUE}=== Dependencies ===${NC}"
    test_case "Database connectivity" test_database_connectivity
    test_case "Redis connectivity" test_redis_connectivity

    # 数据库
    echo ""
    echo -e "${BLUE}=== Database ===${NC}"
    test_case "Migrations applied" test_migrations_applied

    # 摘要
    echo ""
    echo "=========================================================="
    echo "Test Summary"
    echo "=========================================================="
    echo "Total tests: $((PASSED + FAILED))"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    if [ $FAILED -gt 0 ]; then
        echo -e "${RED}Failed: $FAILED${NC}"
    fi
    echo ""

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All staging validation tests passed${NC}"
        echo ""
        echo "This proves only the configured staging target passed. Production promotion still requires verify-candidate.sh."
        return 0
    else
        echo -e "${RED}✗ Some validation tests failed${NC}"
        echo ""
        echo "Please fix the issues before promoting to production."
        return 1
    fi
}

# 检查 curl 是否可用
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is not installed${NC}"
    exit 1
fi

# 检查连接
echo "Checking connectivity to staging..."
if ! curl -s -m 5 "$STAGING_URL/health" >/dev/null 2>&1; then
    echo -e "${RED}Error: Cannot connect to staging environment at $STAGING_URL${NC}"
    echo "Make sure:"
    echo "  1. Staging environment is running"
    echo "  2. STAGING_HOST is correct: $STAGING_HOST"
    echo "  3. Network connectivity is available"
    exit 1
fi

echo -e "${GREEN}✓ Connected to staging${NC}"

main
