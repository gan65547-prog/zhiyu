#!/bin/bash

# Qdrant向量数据库启动脚本
# 用途: 启动Qdrant服务用于文档向量化和RAG检索

echo "🚀 正在启动Qdrant向量数据库..."

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker未运行,请先启动Docker Desktop"
    echo "   执行: open -a Docker"
    exit 1
fi

# 检查Qdrant容器是否已存在
if docker ps -a | grep -q qdrant; then
    echo "📦 Qdrant容器已存在,正在启动..."
    docker start qdrant
else
    echo "📦 创建并启动Qdrant容器..."
    docker run -d \
        --name qdrant \
        -p 6333:6333 \
        -v "$(pwd)/qdrant_data:/qdrant/storage" \
        qdrant/qdrant:latest
fi

# 等待服务启动
echo "⏳ 等待Qdrant服务启动..."
sleep 5

# 验证服务状态
if curl -s http://localhost:6333/health > /dev/null; then
    echo "✅ Qdrant服务启动成功!"
    echo "   健康检查: http://localhost:6333/health"
    echo "   Web UI: http://localhost:6333/dashboard"
else
    echo "❌ Qdrant服务启动失败,请检查Docker日志:"
    echo "   docker logs qdrant"
    exit 1
fi
