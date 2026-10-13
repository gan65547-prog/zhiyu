## syntax=docker/dockerfile:1.7
# 不在此使用 RUN --mount=type=cache：部分 Linux 仅装 docker.io、无 buildx/BuildKit 时无法构建。
# 若 pip 解析失败，请在 Docker Engine 中配置 dns，或设置构建参数 PIP_INDEX_URL 指向国内镜像。
#
# 使用 DaoCloud 镜像源作为备选
FROM docker.m.daocloud.io/library/python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_PREFER_BINARY=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /build

ARG PIP_INDEX_URL=""
ARG PIP_EXTRA_INDEX_URL=""

COPY requirements/runtime.txt requirements/runtime.txt
# 对 Linux ARM，先固定从 PyTorch CPU 索引装 torch，避免 sentence-transformers 触发 CUDA 依赖链。
RUN python -m venv /opt/venv \
    && if [ -n "$PIP_INDEX_URL" ]; then /opt/venv/bin/pip config set global.index-url "$PIP_INDEX_URL"; fi \
    && if [ -n "$PIP_EXTRA_INDEX_URL" ]; then /opt/venv/bin/pip config set global.extra-index-url "$PIP_EXTRA_INDEX_URL"; fi \
    && /opt/venv/bin/pip install --retries 8 --timeout 600 "pip>=24.2,<25" \
    && /opt/venv/bin/pip cache purge || true \
    && /opt/venv/bin/pip install --no-cache-dir --retries 15 --timeout 600 --index-url https://download.pytorch.org/whl/cpu torch==2.11.0 \
    && /opt/venv/bin/pip install --no-cache-dir --retries 15 --timeout 600 -r requirements/runtime.txt

FROM docker.m.daocloud.io/library/node:20-bookworm-slim AS frontend-builder

WORKDIR /frontend
ARG NPM_CONFIG_REGISTRY=""

COPY frontend/package*.json ./
RUN if [ -n "$NPM_CONFIG_REGISTRY" ]; then npm config set registry "$NPM_CONFIG_REGISTRY"; fi \
    && npm ci

COPY frontend/ ./
RUN npm run build:prod

FROM docker.m.daocloud.io/library/python:3.11-slim-bookworm AS runtime

ARG APP_VERSION=unknown
ARG IMAGE_TAG=unknown
ARG RELEASE_GIT_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION} \
    IMAGE_TAG=${IMAGE_TAG} \
    RELEASE_GIT_SHA=${RELEASE_GIT_SHA}

WORKDIR /app

# 图片素材和扫描型 PDF 需要真实 OCR 运行时。固定 Bookworm 是为了让 ARM64
# 镜像使用稳定的软件源，并同时安装中文/英文语言包；缺少这些依赖时，
# Python 适配层只能正确报告失败，无法完成截图入库。
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# 可选：构建时预下载 BGE 模型到镜像，降低运行期外网依赖
ARG PRELOAD_BGE_MODEL=1
ENV HF_HOME=/opt/model-cache/huggingface \
    TRANSFORMERS_CACHE=/opt/model-cache/huggingface/transformers \
    SENTENCE_TRANSFORMERS_HOME=/opt/model-cache/sentence_transformers \
    EMBEDDING_MODEL_PATH=/opt/models/bge-small-zh-v1.5
RUN mkdir -p /opt/models /opt/model-cache/huggingface /opt/model-cache/sentence_transformers

# 本地预置 BGE 模型（构建机 models/ 目录存在时直接打入镜像，免外网下载）
COPY models/bge-small-zh-v1.5 /opt/models/bge-small-zh-v1.5

# 验证模型完整性：检查权重文件存在且大小合理（bge-small-zh 约 91MB）。
# 模型目录不强制存在：生产构建可通过构建上下文提供预置模型，或在
# PRELOAD_BGE_MODEL=1 时从 HuggingFace 镜像预下载；PRELOAD_BGE_MODEL=0
# 用于不希望构建阶段联网的 worker/快速验证镜像。
RUN mkdir -p /opt/models/bge-small-zh-v1.5 && \
    if [ -f /opt/models/bge-small-zh-v1.5/model.safetensors ]; then \
      size=$(stat -c%s /opt/models/bge-small-zh-v1.5/model.safetensors 2>/dev/null) && \
      if [ "$size" -ge 50000000 ]; then \
        echo "✓ Model verification passed: model.safetensors ($size bytes)"; \
      else \
        echo "WARNING: model.safetensors too small ($size bytes), will re-download" >&2; \
        rm -rf /opt/models/bge-small-zh-v1.5/*; \
      fi \
    elif [ "${PRELOAD_BGE_MODEL}" = "1" ]; then \
      echo "WARNING: model.safetensors not found locally, will download from HuggingFace mirror" >&2; \
      echo "Downloading BGE model from HuggingFace mirror..." && \
      python3 -c " \
from sentence_transformers import SentenceTransformer; \
import os; \
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'; \
os.environ['SENTENCE_TRANSFORMERS_HOME'] = '/opt/model-cache/sentence_transformers'; \
model = SentenceTransformer('BAAI/bge-small-zh-v1.5'); \
model.save('/opt/models/bge-small-zh-v1.5'); \
" && echo "✓ Model downloaded and saved to /opt/models/bge-small-zh-v1.5"; \
    else \
      echo "Skipping BGE preload (PRELOAD_BGE_MODEL=${PRELOAD_BGE_MODEL})"; \
    fi && \
    ls -la /opt/models/bge-small-zh-v1.5/

# 仅复制运行所需目录，开发脚本/测试/日志不进入镜像
COPY alembic alembic
COPY alembic.ini .
COPY api api
COPY apps apps
COPY core core
COPY infrastructure infrastructure
COPY services services
COPY static static
COPY templates templates
COPY main.py .
COPY scripts/container /app/startup
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

RUN mkdir -p /app/runtime/logs /app/runtime/data /app/runtime/tmp /app/shared/logs \
    && chmod +x /app/startup/*.sh

EXPOSE 8000

# 配置通过容器环境变量注入（docker-compose / K8s env）；不 COPY .env，避免密钥固化在镜像层
CMD ["/app/startup/run-app.sh"]
