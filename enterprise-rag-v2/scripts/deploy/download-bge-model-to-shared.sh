#!/usr/bin/env bash
# 在部署机（与 docker-compose 同目录）执行：把 BGE 模型下载到 ./shared/models，供 web/worker 挂载使用。
# 适用：镜像构建时未 PRELOAD BGE，或希望模型与镜像解耦、可更新。
#
# 用法：
#   cd /path/to/enterprise-rag-v2   # 含 shared/ 与 .env 的目录
#   ./scripts/deploy/download-bge-model-to-shared.sh
#
# 可选环境变量：
#   WEB_IMAGE=enterprise-rag-v2-web:v1.0.0   # 与本机 docker images 中 tag 一致
#   HF_ENDPOINT=https://hf-mirror.com
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${ROOT}"

mkdir -p shared/models
IMAGE="${WEB_IMAGE:-}"
if [[ -z "${IMAGE}" ]]; then
  IMAGE="$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^enterprise-rag-v2-web:' | head -1 || true)"
fi
if [[ -z "${IMAGE}" ]]; then
  echo "未找到 enterprise-rag-v2-web 镜像，请设置 WEB_IMAGE=repo:tag" >&2
  exit 1
fi

HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
OUT="/app/shared/models/bge-small-zh-v1.5"

echo "使用镜像: ${IMAGE}"
echo "下载到宿主机: ${ROOT}/shared/models/bge-small-zh-v1.5 (HF_ENDPOINT=${HF_ENDPOINT})"

docker run --rm \
  -v "${ROOT}/shared:/app/shared" \
  -e HF_ENDPOINT="${HF_ENDPOINT}" \
  -e HF_HOME=/tmp/hf-cache \
  -e SENTENCE_TRANSFORMERS_HOME=/tmp/st-cache \
  -e TRANSFORMERS_CACHE=/tmp/hf-cache/transformers \
  "${IMAGE}" \
  python -c "
from pathlib import Path
from sentence_transformers import SentenceTransformer
Path('/app/shared/models').mkdir(parents=True, exist_ok=True)
SentenceTransformer('BAAI/bge-small-zh-v1.5').save('${OUT}')
print('saved', '${OUT}')
"

echo "完成。请在 .env 中设置: EMBEDDING_MODEL_PATH=/app/shared/models/bge-small-zh-v1.5 后执行 docker compose up -d。"
