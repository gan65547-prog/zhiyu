#!/usr/bin/env bash
# 构建 enterprise-rag-v2 镜像（默认使用 Dockerfile 内 BuildKit pip 缓存，重复构建最快）
#
# 提速要点：
# - 仅改业务代码、未改 requirements/runtime.txt 时，pip 层会命中缓存，通常只需几秒～一两分钟。
# - 勿随意 docker builder prune / docker system prune -a，会清掉构建缓存，下次又要全量下依赖。
# - 国内网络：PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ./scripts/deploy/build-image.sh
# - 前端 npm 慢：NPM_CONFIG_REGISTRY=https://registry.npmmirror.com ./scripts/deploy/build-image.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# 若构建报 torch wheel invalid，可先: pip cache remove torch

pull_with_fallback() {
  local target_image="$1"
  local mirror_image="$2"
  local aliyun_mirror="$3"
  local ustc_mirror="$4"
  if docker image inspect "${target_image}" >/dev/null 2>&1; then
    echo "本地已存在 ${target_image}，跳过拉取"
    return 0
  fi
  echo "本地无 ${target_image}，尝试从官方源拉取..."
  if docker pull "${target_image}"; then
    return 0
  fi
  if [[ -n "${mirror_image}" ]]; then
    echo "官方源拉取失败，尝试从 DaoCloud 镜像源拉取..."
    if docker pull "${mirror_image}"; then
      docker tag "${mirror_image}" "${target_image}"
      return 0
    fi
  fi
  if [[ -n "${aliyun_mirror}" ]]; then
    echo "DaoCloud 镜像源拉取失败，尝试从阿里云镜像源拉取..."
    if docker pull "${aliyun_mirror}"; then
      docker tag "${aliyun_mirror}" "${target_image}"
      return 0
    fi
  fi
  if [[ -n "${ustc_mirror}" ]]; then
    echo "阿里云镜像源拉取失败，尝试从中科大镜像源拉取..."
    if docker pull "${ustc_mirror}"; then
      docker tag "${ustc_mirror}" "${target_image}"
      return 0
    fi
  fi
  echo "错误：无法拉取 ${target_image} 及其镜像源"
  echo "请检查网络连接，或手动拉取镜像："
  echo "  docker pull ${target_image}"
  echo "或使用其他镜像源："
  echo "  docker pull docker.m.daocloud.io/library/${target_image}"
  echo "  docker tag docker.m.daocloud.io/library/${target_image} ${target_image}"
  echo "  或"
  echo "  docker pull registry.cn-hangzhou.aliyuncs.com/library/${target_image}"
  echo "  docker tag registry.cn-hangzhou.aliyuncs.com/library/${target_image} ${target_image}"
  echo "  或"
  echo "  docker pull docker.mirrors.ustc.edu.cn/library/${target_image}"
  echo "  docker tag docker.mirrors.ustc.edu.cn/library/${target_image} ${target_image}"
  echo ""
  echo "如果所有镜像源都失败，您可以尝试："
  echo "1. 检查网络连接是否正常"
  echo "2. 检查 Docker 配置是否正确"
  echo "3. 尝试使用 VPN 或代理服务器"
  echo "4. 手动下载镜像并导入"
  echo ""
  echo "Dockerfile 中需要这些基础镜像来构建应用，无法跳过此步骤。"
  echo "请确保您能够成功拉取这些镜像后再尝试构建。"
  return 1
}

# 中科大等镜像偶发 EOF 时，可先拉取 DaoCloud 基础镜像并打 tag
pull_with_fallback "python:3.11-slim" "docker.m.daocloud.io/library/python:3.11-slim" "registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim" "docker.mirrors.ustc.edu.cn/library/python:3.11-slim"
pull_with_fallback "node:20-bookworm-slim" "docker.m.daocloud.io/library/node:20-bookworm-slim" "registry.cn-hangzhou.aliyuncs.com/library/node:20-bookworm-slim" "docker.mirrors.ustc.edu.cn/library/node:20-bookworm-slim"

export DOCKER_BUILDKIT=1

# 默认使用清华 PyPI 镜像源，提高国内下载速度和稳定性
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmmirror.com}"

docker build \
  --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}" \
  --build-arg "PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL:-}" \
  --build-arg "NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}" \
  --build-arg "PRELOAD_BGE_MODEL=${PRELOAD_BGE_MODEL:-0}" \
  -t enterprise-rag-v2:latest \
  .

# 同一 Dockerfile 产出两套镜像名，便于编排区分 web / worker 职责
docker tag enterprise-rag-v2:latest enterprise-rag-v2-web:latest
docker tag enterprise-rag-v2:latest enterprise-rag-v2-worker:latest

echo "完成: enterprise-rag-v2:latest（已同步 tag 为 enterprise-rag-v2-web:latest / enterprise-rag-v2-worker:latest）"
