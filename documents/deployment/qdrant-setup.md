# Qdrant向量数据库启动指南

## 📋 概述

Qdrant是本系统使用的向量数据库,用于存储文档向量和执行相似度检索。本文档提供详细的启动和配置指南。

---

## 🚀 快速启动

### 方法1: 使用启动脚本 (推荐)

```bash
cd enterprise-rag-v2
./scripts/start_qdrant.sh
```

### 方法2: 使用Docker Desktop GUI

1. **打开Docker Desktop**
   ```bash
   open -a Docker
   ```

2. **在Docker Desktop中操作**:
   - 点击顶部搜索栏
   - 搜索 `qdrant/qdrant`
   - 点击 "Pull" 拉取镜像

3. **创建容器**:
   - 点击 "Images" 标签
   - 找到 `qdrant/qdrant` 镜像
   - 点击 "Run" 按钮
   - 配置容器:
     - Container name: `qdrant`
     - Ports: `6333:6333`
     - Volumes: `./qdrant_data:/qdrant/storage`
   - 点击 "Run" 启动

### 方法3: 使用docker-compose

```bash
cd enterprise-rag-v2
docker-compose up -d qdrant
```

### 方法4: 手动Docker命令

```bash
cd enterprise-rag-v2

# 创建数据目录
mkdir -p qdrant_data

# 启动容器
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v "$(pwd)/qdrant_data:/qdrant/storage" \
  qdrant/qdrant:latest
```

---

## ✅ 验证服务状态

### 1. 健康检查

```bash
curl http://localhost:6333/health
```

**预期输出**:
```json
{
  "title": "qdrant - vector search engine",
  "version": "1.x.x"
}
```

### 2. 访问Web UI

打开浏览器访问: http://localhost:6333/dashboard

### 3. 检查容器状态

```bash
docker ps | grep qdrant
```

**预期输出**:
```
CONTAINER ID   IMAGE              STATUS         PORTS
xxxxx          qdrant/qdrant      Up 5 minutes   0.0.0.0:6333->6333/tcp
```

---

## 🔧 常见问题排查

### 问题1: 端口被占用

**现象**:
```
Error: port 6333 is already in use
```

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :6333

# 停止旧的Qdrant容器
docker stop qdrant
docker rm qdrant

# 重新启动
./scripts/start_qdrant.sh
```

### 问题2: Docker未运行

**现象**:
```
Cannot connect to the Docker daemon
```

**解决方案**:
```bash
# 启动Docker Desktop
open -a Docker

# 等待Docker启动完成(约30秒)
sleep 30

# 重新启动Qdrant
./scripts/start_qdrant.sh
```

### 问题3: 数据目录权限问题

**现象**:
```
Permission denied: /qdrant/storage
```

**解决方案**:
```bash
# 修改数据目录权限
chmod -R 755 qdrant_data

# 重启容器
docker restart qdrant
```

### 问题4: 容器启动失败

**现象**:
```
Container qdrant exited with code 1
```

**解决方案**:
```bash
# 查看容器日志
docker logs qdrant

# 删除容器和数据,重新开始
docker rm -f qdrant
rm -rf qdrant_data
./scripts/start_qdrant.sh
```

---

## 📊 性能配置

### 生产环境配置

编辑 `docker-compose.yml`:

```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"
  volumes:
    - qdrant_data:/qdrant/storage
  environment:
    # 内存限制
    - QDRANT__SERVICE__MAX_REQUEST_SIZE_MB=100
    # 并发配置
    - QDRANT__SERVICE__MAX_WORKERS=4
    # 日志级别
    - QDRANT__LOG_LEVEL=INFO
  deploy:
    resources:
      limits:
        memory: 4G
        cpus: '2'
```

### 索引优化配置

在创建集合时配置:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url="http://localhost:6333")

# 创建集合(优化配置)
client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(
        size=1536,  # 向量维度
        distance=Distance.COSINE,  # 相似度计算方式
    ),
    # HNSW索引配置(提升检索速度)
    hnsw_config={
        "m": 16,  # 连接数(越大越精确,但内存占用越高)
        "ef_construct": 100,  # 构建时搜索深度
    },
    # 优化器配置
    optimizers_config={
        "default_segment_number": 2,  # 段数量
        "indexing_threshold": 20000,  # 索引阈值
    }
)
```

---

## 🔄 数据备份与恢复

### 备份数据

```bash
# 推荐：使用 Snapshot API 热备（无需停服务）
COLLECTION="documents"
SNAPSHOT_NAME=$(curl -s -X POST "http://localhost:6333/collections/$COLLECTION/snapshots" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])')

curl -o "qdrant_${COLLECTION}_${SNAPSHOT_NAME}.snapshot" \
  "http://localhost:6333/collections/$COLLECTION/snapshots/$SNAPSHOT_NAME"
```

### 恢复数据

```bash
# 从 snapshot 恢复（示例）
COLLECTION="documents"
SNAPSHOT_FILE="qdrant_${COLLECTION}_2026-04-10.snapshot"

curl -X POST "http://localhost:6333/collections/$COLLECTION/snapshots/upload" \
  -F "snapshot=@$SNAPSHOT_FILE"
```

---

## 📈 监控指标

### 查看集合信息

```bash
curl http://localhost:6333/collections
```

### 查看集群信息

```bash
curl http://localhost:6333/cluster
```

### 查看指标

```bash
curl http://localhost:6333/metrics
```

---

## 🔗 相关资源

- [Qdrant官方文档](https://qdrant.tech/documentation/)
- [Qdrant GitHub](https://github.com/qdrant/qdrant)
- [Qdrant Docker Hub](https://hub.docker.com/r/qdrant/qdrant)

---

## 📞 技术支持

如遇到问题,请:
1. 查看容器日志: `docker logs qdrant`
2. 查看系统日志: `tail -f logs/app.log`
3. 联系技术支持团队

---

**文档版本**: v1.0  
**最后更新**: 2026-04-02
