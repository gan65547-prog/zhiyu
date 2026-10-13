#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-/app/shared/logs}"
MAX_AGE_DAYS="${LOG_MAX_AGE_DAYS:-7}"
MAX_TOTAL_BYTES="${LOG_MAX_TOTAL_BYTES:-2147483648}" # 2 GiB
CHECK_INTERVAL_SECONDS="${LOG_MAINTENANCE_INTERVAL_SECONDS:-3600}"

mkdir -p "${LOG_DIR}"

cleanup_once() {
  # 1) 先清理过期文件（7天）
  find "${LOG_DIR}" -type f -mtime +"${MAX_AGE_DAYS}" -delete 2>/dev/null || true

  # 2) 控制总大小（2G），超过则从最老文件开始删
  local total
  total="$(du -sb "${LOG_DIR}" 2>/dev/null | awk '{print $1}')"
  total="${total:-0}"

  while [ "${total}" -gt "${MAX_TOTAL_BYTES}" ]; do
    local oldest
    oldest="$(ls -1tr "${LOG_DIR}" 2>/dev/null | head -n 1 || true)"
    [ -n "${oldest}" ] || break
    rm -f "${LOG_DIR}/${oldest}" || true
    total="$(du -sb "${LOG_DIR}" 2>/dev/null | awk '{print $1}')"
    total="${total:-0}"
  done
}

while true; do
  cleanup_once
  sleep "${CHECK_INTERVAL_SECONDS}"
done
