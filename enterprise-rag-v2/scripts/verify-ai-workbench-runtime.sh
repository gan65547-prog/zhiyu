#!/usr/bin/env bash
set -euo pipefail

# 只读运行时验收：不启动、停止、迁移或修改任何服务。
# 用法：bash scripts/verify-ai-workbench-runtime.sh [compose 文件] [API 地址]

COMPOSE_FILE="${1:-docker-compose.yml}"
API_URL="${2:-http://localhost:8000}"

if ! command -v docker >/dev/null 2>&1; then
  echo "FAIL: 未找到 docker 命令" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "BLOCKED: Docker daemon 不可用，请先启动 Docker" >&2
  exit 2
fi

mapfile -t declared_services < <(docker compose -f "$COMPOSE_FILE" config --services)
mapfile -t running_services < <(docker compose -f "$COMPOSE_FILE" ps --status running --services)

required_services=(db redis qdrant web worker beat)
for service in "${required_services[@]}"; do
  if ! printf '%s\n' "${declared_services[@]}" | grep -Fxq "$service"; then
    echo "FAIL: Compose 未声明必需服务: $service" >&2
    exit 1
  fi
  if ! printf '%s\n' "${running_services[@]}" | grep -Fxq "$service"; then
    echo "FAIL: 必需服务未运行: $service" >&2
    exit 1
  fi
done

if ! curl --fail --silent --show-error --max-time 10 "$API_URL/health/ready" >/dev/null; then
  echo "FAIL: API readiness 检查失败: $API_URL/health/ready" >&2
  exit 1
fi

echo "PASS: AI 工作台运行时服务与 API readiness 均已就绪"
