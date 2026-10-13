#!/usr/bin/env bash
set -euo pipefail

echo "== in-container release fields =="
echo "APP_VERSION=${APP_VERSION:-}"
echo "IMAGE_TAG=${IMAGE_TAG:-${APP_VERSION:-}}"
echo "RELEASED_AT=${RELEASED_AT:-}"
echo "RELEASE_GIT_TAG=${RELEASE_GIT_TAG:-}"
echo "RELEASE_GIT_SHA=${RELEASE_GIT_SHA:-}"

echo
echo "== startup scripts =="
ls -1 /app/startup 2>/dev/null || true

echo
echo "== logs dir =="
ls -lh /app/shared/logs 2>/dev/null || true
