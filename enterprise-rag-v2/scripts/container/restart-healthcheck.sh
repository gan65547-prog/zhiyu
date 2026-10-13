#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health/live}"
RETRY_MAX="${RETRY_MAX:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-2}"

/app/startup/stop-app.sh
/app/startup/start-app.sh

for i in $(seq 1 "${RETRY_MAX}"); do
  if python3 - <<PY
import urllib.request
u="${HEALTH_URL}"
r=urllib.request.urlopen(u, timeout=5)
raise SystemExit(0 if r.status == 200 else 1)
PY
  then
    echo "[restart-healthcheck] health check passed"
    exit 0
  fi
  sleep "${RETRY_INTERVAL}"
done

echo "[restart-healthcheck] health check failed"
exit 1
