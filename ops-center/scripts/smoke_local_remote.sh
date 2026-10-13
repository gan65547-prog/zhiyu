#!/usr/bin/env bash
# ops-center + 配置的业务服务：冒烟联通性
# 用法：在 ops-center 目录配置 .env 后执行 bash scripts/smoke_local_remote.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

_load_simple() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^BUSINESS_BASE_URL= ]]; then
      export BUSINESS_BASE_URL="${line#BUSINESS_BASE_URL=}"
      export BUSINESS_BASE_URL="${BUSINESS_BASE_URL//\"/}"
    fi
    if [[ "$line" =~ ^INTERNAL_API_KEY= ]]; then
      export INTERNAL_API_KEY="${line#INTERNAL_API_KEY=}"
      export INTERNAL_API_KEY="${INTERNAL_API_KEY//\"/}"
    fi
  done <"$f"
}

_load_simple .env

BUSINESS="${BUSINESS_BASE_URL:-http://127.0.0.1:8000}"
: "${INTERNAL_API_KEY:?Set INTERNAL_API_KEY in .env or the environment (must match the business service key)}"

echo "== 1) 业务 ${BUSINESS}/health/live =="
curl -sfS "${BUSINESS}/health/live" | head -c 200
echo ""

echo "== 2) /internal/admin/tenants（密钥+白名单）=="
RID="smoke-$(date +%s)"
code="$(curl -s -o /tmp/ops_smoke.json -w "%{http_code}" \
  -H "X-Request-Id: ${RID}" \
  -H "X-Internal-Api-Key: ${INTERNAL_API_KEY}" \
  -H "Accept: application/json" \
  "${BUSINESS}/internal/admin/tenants?page=1&page_size=10" || true)"
echo "HTTP ${code}"
if [[ "${code}" != "200" ]]; then
  cat /tmp/ops_smoke.json 2>/dev/null || true
  echo ""
  echo "401/403 时：检查 127.0.0.1 上 INTERNAL_API_KEYS、INTERNAL_IP_WHITELIST（放行调用方 IP 或先用 *）"
  exit 1
fi
head -c 1 /tmp/ops_smoke.json | grep -q '{' || {
  echo "响应体不是 JSON（常见为前端 SPA HTML）：请确认 127.0.0.1 已部署包含 /internal/admin 的版本，或路由未被静态页兜底。"
  head -c 400 /tmp/ops_smoke.json
  echo ""
  rm -f /tmp/ops_smoke.json
  exit 1
}
rm -f /tmp/ops_smoke.json
echo "内部接口联通 OK（JSON）"

echo "== 3) ops-center http://127.0.0.1:8081/health/live =="
curl -sfS "http://127.0.0.1:8081/health/live" >/dev/null && echo OK || {
  echo "请先启动 ops-center（本机 8081）"
  exit 1
}
echo "冒烟完成"
