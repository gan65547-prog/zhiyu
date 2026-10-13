#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/app/shared/logs}"

mkdir -p "${LOG_DIR}" /app/runtime/tmp
cd "${APP_DIR}"

# 数据库迁移：每次启动自动执行，保证 schema 与代码同步
/app/startup/run-migrations.sh

# 后台日志清理守护：7天或2G阈值自动清理
/app/startup/log-maintenance.sh &

# 前台运行主进程（容器生命周期绑定）
exec gunicorn main:app \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout "${GUNICORN_TIMEOUT:-180}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-60}" \
  --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
  --pid /app/runtime/tmp/gunicorn.pid \
  --access-logfile "${LOG_DIR}/gunicorn-access.log" \
  --error-logfile "${LOG_DIR}/gunicorn-error.log"
