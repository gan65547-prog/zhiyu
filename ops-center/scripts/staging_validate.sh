#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"
TENANT_ID="${TENANT_ID:-test-tenant}"
OPERATOR="${OPERATOR:-ops-center-staging}"
OP_PREFIX="${OP_PREFIX:-ops-staging-$(date +%Y%m%d%H%M%S)}"
OUT_DIR="${OUT_DIR:-./reports}"
OUT_FILE="${OUT_FILE:-${OUT_DIR}/staging-validation-$(date +%Y%m%d-%H%M%S).md}"

mkdir -p "${OUT_DIR}"

run_json() {
  local name="$1"
  shift
  local tmp
  tmp="$(mktemp)"
  local code
  code=$(curl -sS -o "${tmp}" -w "%{http_code}" "$@" || true)
  {
    echo "### ${name}"
    echo
    echo "- HTTP: \`${code}\`"
    echo
    echo '```json'
    cat "${tmp}"
    echo
    echo '```'
    echo
  } >> "${OUT_FILE}"
  rm -f "${tmp}"
}

{
  echo "# ops-center Staging 联调记录"
  echo
  echo "- 时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- BASE_URL: \`${BASE_URL}\`"
  echo "- TENANT_ID: \`${TENANT_ID}\`"
  echo "- OPERATOR: \`${OPERATOR}\`"
  echo "- OP_PREFIX: \`${OP_PREFIX}\`"
  echo
  echo "## 结果明细"
  echo
} > "${OUT_FILE}"

run_json "Health Live" \
  "${BASE_URL}/health/live"

run_json "Health Ready" \
  "${BASE_URL}/health/ready"

run_json "Health Upstream" \
  "${BASE_URL}/api/v1/operations/health/upstream"

run_json "List Tenants" \
  "${BASE_URL}/api/v1/operations/tenants?page=1&page_size=10"

run_json "List Operations" \
  "${BASE_URL}/api/v1/operations?page=1&page_size=10"

run_json "List Audit Logs" \
  "${BASE_URL}/api/v1/operations/audit/logs?page=1&page_size=10"

run_json "Quota Update" \
  -X POST "${BASE_URL}/api/v1/operations/tenants/${TENANT_ID}/quota" \
  -H "Content-Type: application/json" \
  -H "X-Op-Id: ${OP_PREFIX}-quota" \
  -H "X-Operator: ${OPERATOR}" \
  -d '{"quota_type":"documents","value":100,"reason":"staging-validate"}'

run_json "Reindex" \
  -X POST "${BASE_URL}/api/v1/operations/documents/reindex" \
  -H "Content-Type: application/json" \
  -H "X-Op-Id: ${OP_PREFIX}-reindex" \
  -H "X-Operator: ${OPERATOR}" \
  -d "{\"tenant_id\":\"${TENANT_ID}\",\"dataset_id\":\"ds-1\"}"

echo "staging validation report generated: ${OUT_FILE}"
