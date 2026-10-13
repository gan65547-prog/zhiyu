#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"
OP_ID="${OP_ID:-ops-smoke-001}"
OPERATOR="${OPERATOR:-ops-center-smoke}"
# 登录凭据由运行环境提供；脚本不保存默认密码。
OPS_LOGIN_USER="${OPS_LOGIN_USER:-admin}"
OPS_LOGIN_PASSWORD="${OPS_LOGIN_PASSWORD:-}"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

require_env() {
  local key="$1"
  if [[ -z "${!key:-}" ]]; then
    echo "missing required env: ${key}" >&2
    exit 2
  fi
}

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[dry-run] checking required environment variables..."
  require_env BASE_URL
  require_env OP_ID
  require_env OPERATOR
  echo "[dry-run] ok (login uses OPS_LOGIN_USER / OPS_LOGIN_PASSWORD if set)"
  exit 0
fi

require_env OPS_LOGIN_PASSWORD

login_and_bearer() {
  local resp token
  resp="$(curl -sS -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${OPS_LOGIN_USER}\",\"password\":\"${OPS_LOGIN_PASSWORD}\"}")"
  token="$(printf '%s' "${resp}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['access_token'])" 2>/dev/null)" || true
  if [[ -z "${token}" ]]; then
    echo "login failed; response:" >&2
    echo "${resp}" >&2
    echo "提示：检查 OPS_LOGIN_USER/OPS_LOGIN_PASSWORD 是否与运维中心引导账号一致。" >&2
    exit 1
  fi
  printf 'Authorization: Bearer %s' "${token}"
}

AUTH_HDR="$(login_and_bearer)"

# 写路径需要真实 tenant_id；可用 TENANT_ID 覆盖，否则从列表接口取第一条
resolve_tenant_id() {
  if [[ -n "${TENANT_ID:-}" ]]; then
    printf '%s' "${TENANT_ID}"
    return
  fi
  local raw tid
  raw="$(curl -sS "${BASE_URL}/api/v1/operations/tenants?page=1&page_size=10" -H "${AUTH_HDR}")"
  tid="$(printf '%s' "${raw}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
items = d.get('data') or []
if not items:
    sys.exit(1)
print(items[0]['id'])
" 2>/dev/null)" || true
  if [[ -z "${tid}" ]]; then
    echo "无法解析租户 ID（上游无租户或返回非预期）；请设置环境变量 TENANT_ID" >&2
    exit 1
  fi
  printf '%s' "${tid}"
}

TENANT_FOR_WRITE="$(resolve_tenant_id)"

echo "[1/6] health"
curl -fsS "$BASE_URL/health/live" >/dev/null
curl -fsS "$BASE_URL/health/ready" >/dev/null
echo "ok"

echo "[2/6] list tenants (read path)"
curl -fsS "$BASE_URL/api/v1/operations/tenants?page=1&page_size=10" \
  -H "${AUTH_HDR}" >/dev/null
echo "ok"

echo "[3/6] quota write path (tenant=${TENANT_FOR_WRITE})"
curl -fsS -X POST "$BASE_URL/api/v1/operations/tenants/${TENANT_FOR_WRITE}/quota" \
  -H "${AUTH_HDR}" \
  -H "Content-Type: application/json" \
  -H "X-Op-Id: ${OP_ID}" \
  -H "X-Operator: ${OPERATOR}" \
  -d '{"quota_type":"documents","value":100,"reason":"smoke"}' >/dev/null
echo "ok"

if [[ -n "${SMOKE_DATASET_ID:-}" ]]; then
  echo "[4/6] reindex write path (dataset=${SMOKE_DATASET_ID})"
  curl -fsS -X POST "$BASE_URL/api/v1/operations/documents/reindex" \
    -H "${AUTH_HDR}" \
    -H "Content-Type: application/json" \
    -H "X-Op-Id: ${OP_ID}-reindex" \
    -H "X-Operator: ${OPERATOR}" \
    -d "{\"tenant_id\":\"${TENANT_FOR_WRITE}\",\"dataset_id\":\"${SMOKE_DATASET_ID}\"}" >/dev/null
  echo "ok"
else
  echo "[4/6] reindex write path — 跳过（未设置 SMOKE_DATASET_ID）"
fi

echo "[5/5] smoke passed"
