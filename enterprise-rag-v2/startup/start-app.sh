#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/app/shared/logs}"
PID_FILE="${PID_FILE:-/app/runtime/tmp/gunicorn.pid}"
BIND_ADDR="${BIND_ADDR:-0.0.0.0:8000}"
WORKERS="${GUNICORN_WORKERS:-2}"

mkdir -p "${LOG_DIR}" "$(dirname "${PID_FILE}")"
cd "${APP_DIR}"

if pgrep -f "gunicorn main:app" >/dev/null 2>&1; then
  echo "[start-app] gunicorn already running"
  exit 0
fi

nohup gunicorn main:app \
  --bind "${BIND_ADDR}" \
  --workers "${WORKERS}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --pid "${PID_FILE}" \
  --access-logfile "${LOG_DIR}/gunicorn-access.log" \
  --error-logfile "${LOG_DIR}/gunicorn-error.log" \
  >> "${LOG_DIR}/launcher.log" 2>&1 &

echo "[start-app] started"
