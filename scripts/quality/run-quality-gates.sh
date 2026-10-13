#!/usr/bin/env bash
# Daily project-neutral gates adapted to Ganfy's Python/RAG services.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$ROOT_DIR/enterprise-rag-v2/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/enterprise-rag-v2/.venv/bin/python"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi
export PYTHON_BIN
OPS_PYTHON_BIN="${OPS_PYTHON_BIN:-}"
if [[ -z "$OPS_PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/ops-center/.venv/bin/python" ]]; then
    OPS_PYTHON_BIN="$ROOT_DIR/ops-center/.venv/bin/python"
  else
    OPS_PYTHON_BIN="$PYTHON_BIN"
  fi
fi
export OPS_PYTHON_BIN
MODE="quick"
case "${1:-}" in
  --full) MODE="full" ;;
  --ci) MODE="ci" ;;
esac
cd "$ROOT_DIR"

failed=0
run() {
  local name="$1"; shift
  if "$@"; then echo "[PASS] $name"; else echo "[FAIL] $name"; failed=$((failed + 1)); fi
}

run "diff whitespace" git diff --check
run "release profile" "$PYTHON_BIN" scripts/quality/check-release-profile.py --profile release/release-profile.json
run "active document links" "$PYTHON_BIN" - <<'PY'
import re
from pathlib import Path
root = Path("documents")
for doc in root.rglob("*.md"):
    if "archive" in doc.parts:
        continue
    for target in re.findall(r"\]\(([^)#]+\.md)(?:#[^)]+)?\)", doc.read_text(encoding="utf-8")):
        if not (doc.parent / target).exists():
            raise SystemExit(f"broken link: {doc} -> {target}")
PY
run "change profile" bash scripts/quality/classify-change-profile.sh
run "code structure" "$PYTHON_BIN" scripts/quality/check-code-structure.py \
  --root enterprise-rag-v2/api \
  --root enterprise-rag-v2/services \
  --root enterprise-rag-v2/core \
  --root enterprise-rag-v2/infrastructure \
  --root ops-center/app \
  --baseline scripts/quality/code-quality-baseline.json
run "frontend structure" "$PYTHON_BIN" scripts/quality/check-frontend-structure.py \
  --root enterprise-rag-v2/frontend/src \
  --repo-root . \
  --baseline scripts/quality/frontend-quality-baseline.json
run "module boundaries" "$PYTHON_BIN" scripts/quality/check-module-boundaries.py \
  --root enterprise-rag-v2/api \
  --root enterprise-rag-v2/services \
  --root enterprise-rag-v2/core \
  --baseline scripts/quality/module-boundary-baseline.json

if [[ "$MODE" != "quick" ]]; then
  run "Python syntax (RAG)" "$PYTHON_BIN" -m compileall -q enterprise-rag-v2/api enterprise-rag-v2/services enterprise-rag-v2/core enterprise-rag-v2/infrastructure
  run "Python syntax (ops center)" "$PYTHON_BIN" -m compileall -q ops-center/app
fi

if [[ "$MODE" == "full" ]]; then
  # Default full regression is deterministic core behavior. Manual, live
  # integration, performance and service-startup probes require explicit
  # infrastructure and are not allowed to make the local gate hang.
  # Keep the gate deterministic: project tests explicitly load pytest-asyncio;
  # unrelated globally installed pytest plugins must not be discovered.
  run "RAG core regression tests" bash -c 'cd enterprise-rag-v2 && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PYTHON_BIN" -m pytest -p pytest_asyncio.plugin tests/api tests/unit tests/security tests/test_preservation.py --ignore=tests/unit/services/test_document_copy_service.py -q --tb=short'
  run "ops-center regression tests" bash -c 'cd ops-center && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$OPS_PYTHON_BIN" -m pytest -p pytest_asyncio.plugin tests -q --tb=short'
fi

(( failed == 0 )) || exit 1
echo "===== QUALITY GATES: ALL PASSED ====="
