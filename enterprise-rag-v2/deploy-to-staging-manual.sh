#!/usr/bin/env bash
# 手动部署脚本
set -euo pipefail

TAG="staging-test"
REMOTE_HOST="${REMOTE_HOST:?Set REMOTE_HOST=user@host}"
REMOTE_DIR="${REMOTE_DIR:?Set REMOTE_DIR to the project directory on the staging host}"

echo "开始部署到预生产环境..."
echo "Tag: $TAG"
echo "目标: $REMOTE_HOST"

# 1. 传输 web 镜像
echo "正在传输 web 镜像..."
docker save "enterprise-rag-v2-web:$TAG" | ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=240 "$REMOTE_HOST" "docker load"
echo "web 镜像传输完成"

# 2. 传输 worker 镜像
echo "正在传输 worker 镜像..."
docker save "enterprise-rag-v2-worker:$TAG" | ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=240 "$REMOTE_HOST" "docker load"
echo "worker 镜像传输完成"

# 3. 在远程部署
echo "正在远程部署..."
ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=240 "$REMOTE_HOST" bash -s <<REMOTE_SCRIPT
set -euo pipefail

cd "$REMOTE_DIR"

# 准备目录
mkdir -p runtime/logs runtime/data runtime/tmp shared/logs

# 创建 docker-compose 文件
cat > docker-compose.deploy.yml <<COMPOSE_EOF
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ragdb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: \${DB_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.12.5
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
    restart: unless-stopped

  web:
    image: enterprise-rag-v2-web:$TAG
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:\${DB_PASSWORD:-postgres}@db:5432/ragdb
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_COLLECTION: documents
      QDRANT_VECTOR_SIZE: 512
      EMBEDDING_MODEL_PATH: /opt/models/bge-small-zh-v1.5
      HF_ENDPOINT: https://hf-mirror.com
      OPENAI_API_KEY: \${OPENAI_API_KEY:-}
      OPENAI_BASE_URL: \${OPENAI_BASE_URL:-https://api.deepseek.com/v1}
      OPENAI_MODEL: \${OPENAI_MODEL:-deepseek-chat}
      DEBUG: "false"
      JWT_SECRET: \$(openssl rand -hex 32)
      CSRF_SECRET: \$(openssl rand -hex 32)
    ports:
      - "8000:8000"
    volumes:
      - ${REMOTE_DIR}/runtime:/app/runtime
      - ${REMOTE_DIR}/runtime/uploads:/app/uploads
      - ${REMOTE_DIR}/shared:/app/shared
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
    restart: unless-stopped

  worker:
    image: enterprise-rag-v2-worker:$TAG
    command: celery -A infrastructure.queue.celery_app.celery_app worker -l INFO --concurrency=4 -Q documents_high,chat_async,celery
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:\${DB_PASSWORD:-postgres}@db:5432/ragdb
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_COLLECTION: documents
      QDRANT_VECTOR_SIZE: 512
      EMBEDDING_MODEL_PATH: /opt/models/bge-small-zh-v1.5
      HF_ENDPOINT: https://hf-mirror.com
      OPENAI_API_KEY: \${OPENAI_API_KEY:-}
      OPENAI_BASE_URL: \${OPENAI_BASE_URL:-https://api.deepseek.com/v1}
      OPENAI_MODEL: \${OPENAI_MODEL:-deepseek-chat}
      JWT_SECRET: \$(openssl rand -hex 32)
      CSRF_SECRET: \$(openssl rand -hex 32)
    volumes:
      - ${REMOTE_DIR}/runtime:/app/runtime
      - ${REMOTE_DIR}/runtime/uploads:/app/uploads
      - ${REMOTE_DIR}/shared:/app/shared
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  qdrant_data:

networks:
  default:
    driver: bridge
COMPOSE_EOF

# 停止旧的容器
docker compose -f docker-compose.deploy.yml down || true

# 启动新的容器
docker compose -f docker-compose.deploy.yml up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "服务状态:"
docker compose -f docker-compose.deploy.yml ps

REMOTE_SCRIPT

echo ""
echo "部署完成！"
echo "请通过部署环境的主机名访问服务。"
echo ""
echo "等待服务完全启动后，可以运行验证脚本"
