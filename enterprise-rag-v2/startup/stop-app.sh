#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${PID_FILE:-/app/runtime/tmp/gunicorn.pid}"

if [ -f "${PID_FILE}" ]; then
  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [ -n "${PID}" ] && kill -0 "${PID}" 2>/dev/null; then
    kill -TERM "${PID}" || true
    sleep 2
  fi
  rm -f "${PID_FILE}" || true
fi

pkill -TERM -f "gunicorn main:app" 2>/dev/null || true
echo "[stop-app] done"
