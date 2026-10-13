# 文档分段向量化问题排查 FAQ

## 概述

本文档记录了本地开发环境（localhost:8000）文档分段向量化问题的完整排查过程和解决方案。

---

## 问题现象

### 1. 文档处理全部失败

**症状**：
- 用户上传文档后，前端显示全部文档状态为"失败"
- 错误提示："处理未成功。可删除该文档后重新上传再试。"

### 2. 文档卡在 PROCESSING 状态

**症状**：
- 部分文档状态显示为"处理中"，但进度停留在 5%
- `processing_phase` 停留在 "extracting" 阶段
- `chunk_count` 有值但文档不再继续处理

### 3. API 与数据库状态不一致

**症状**：
- API 返回的文档状态统计与数据库实际状态不符
- 例如：API 返回 4 pending，数据库显示 3 PROCESSING + 1 PENDING

---

## 问题根因分析

### 根因 1：Worker 容器缺少 uploads 目录挂载

**问题描述**：
```yaml
# 错误配置（修复前）
web:
  volumes:
    - ./runtime:/app/runtime
    - ./runtime/uploads:/app/uploads  # 错误：独立挂载uploads
    
worker:
  volumes:
    - ./runtime:/app/runtime
    - ./runtime/uploads:/app/uploads  # 错误：独立挂载uploads
```

**影响**：
- Web 容器上传文件到 `/app/runtime/uploads/`
- Worker 容器虽然也挂载了 uploads，但路径映射不一致
- Worker 处理文档时报错："源文件不存在: /app/uploads/xxx.epub"

**根本原因**：
- `./runtime:/app/runtime` 已经将整个 runtime 目录（包含 uploads 子目录）挂载到容器
- 额外挂载 `./runtime/uploads:/app/uploads` 导致路径混乱
- Worker 实际应该在 `/app/runtime/uploads/` 访问文件，但代码查找的是 `/app/uploads/`

**解决方案**：
```yaml
# 正确配置（修复后）
web:
  volumes:
    - ./runtime:/app/runtime      # 包含 uploads 子目录
    - ./shared:/app/shared        # 共享目录（日志、模型等）
    
worker:
  volumes:
    - ./runtime:/app/runtime      # 与 web 保持一致
    - ./shared:/app/shared        # 与 web 保持一致
```

**验证方法**：
```bash
# 检查 worker 是否能访问上传的文件
docker exec <worker_container> ls -la /app/runtime/uploads/

# 应该看到与 web 容器相同的文件列表
docker exec <web_container> ls -la /app/runtime/uploads/
```

---

### 根因 2：向量存储失败被静默处理

**问题描述**：
- Qdrant upsert 操作失败时，错误被 `except` 捕获但未正确处理
- 文档状态仍被设置为 `COMPLETED`，但 Qdrant 中实际没有向量数据
- 用户以为文档处理成功，但检索时找不到内容

**影响**：
- 已完成处理的文档（如 `test_rag2.txt`）segment_count=1
- 但 Qdrant 集合中 `indexed_vectors_count: 0`
- 前端无法检索到文档内容

**根本原因**：
```python
# 错误代码（修复前）
try:
    await vector_store.upsert(pending_points)
except Exception as e:
    logger.error(f"向量存储失败: {e}")  # 仅记录日志
# 继续执行，文档状态被设置为 COMPLETED
```

**解决方案**：
```python
# 正确代码（修复后）
vector_store_success = True
if pending_points:
    try:
        success = await vector_store.upsert(pending_points)
        if not success:
            vector_store_success = False
            logger.error(f"向量存储失败: upsert 返回 False")
        else:
            upserted_vectors += len(pending_points)
    except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
        vector_store_success = False
        logger.error(f"向量存储失败: {e}", exc_info=True)

# 检查向量存储是否成功
if not vector_store_success:
    document.status = DocumentStatus.FAILED
    error_reason = "向量存储失败，文档分段已创建但向量未索引"
    document_meta = document.extra_metadata or {}
    processing_meta = (document_meta.get("processing") or {})
    processing_meta["error_reason"] = error_reason
    document_meta["processing"] = processing_meta
    document.extra_metadata = document_meta
```

**影响范围**：
- 修复前已标记为 COMPLETED 但向量存储失败的文档
- 这些文档需要删除后重新上传

---

### 根因 3：僵尸任务导致文档卡在 PROCESSING 状态

**问题描述**：
- 3 个文档状态为 PROCESSING，但进度停留在 5%
- 更新时间停留在部署时间点（02:41:22）
- Worker 日志显示没有正在处理的任务

**影响**：
- 用户无法对这些文档进行任何操作
- 前端显示"处理中"，但实际处理已停止

**根本原因**：
- Celery worker 在处理文档时被容器重启中断
- 文档状态已更新为 PROCESSING，但任务未完成
- Redis 队列中没有待处理任务（任务已被消费但未完成）
- 形成"僵尸任务"

**解决方案**：
```bash
# 方案 1：使用 reindex API 重新触发处理
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/reindex"

# 方案 2：删除后重新上传
# 在数据库中删除卡住的文档
DELETE FROM documents WHERE status = 'PROCESSING';
# 或通过前端删除文档后重新上传
```

---

## 排查步骤总结

### 1. 检查服务健康状态

```bash
# 检查 API 服务
curl http://localhost:8000/health

# 检查 Qdrant 服务
curl http://localhost:6333/health

# 检查 Redis 服务
docker exec enterprise-rag-v2-redis-1 redis-cli ping
```

### 2. 检查容器状态

```bash
# 查看所有容器
docker ps

# 查看 worker 容器日志
docker logs enterprise-rag-v2-worker-1 --tail 100

# 查看 worker 容器内的文件
docker exec enterprise-rag-v2-worker-1 ls -la /app/runtime/uploads/
```

### 3. 检查数据库状态

```bash
# 查看文档状态分布
docker exec enterprise-rag-v2-db-1 psql -U postgres -d ragdb -c \
  "SELECT status, COUNT(*) FROM documents GROUP BY status;"

# 查看卡住的 PROCESSING 文档
docker exec enterprise-rag-v2-db-1 psql -U postgres -d ragdb -c \
  "SELECT file_name, status, chunk_count, updated_at 
   FROM documents 
   WHERE status = 'PROCESSING' 
   ORDER BY updated_at DESC;"
```

### 4. 检查 Redis 队列

```bash
# 查看待处理任务数量
docker exec enterprise-rag-v2-redis-1 redis-cli LLEN documents_high
docker exec enterprise-rag-v2-redis-1 redis-cli LLEN celery

# 查看队列中的任务
docker exec enterprise-rag-v2-redis-1 redis-cli LRANGE documents_high 0 50
```

### 5. 检查 Qdrant 向量数据

```bash
# 查看所有集合
curl http://localhost:6333/collections

# 查看特定集合的向量数量
curl http://localhost:6333/collections/documents_xxx/points/search \
  -H "Content-Type: application/json" \
  -d '{"vector": [0.1]*512, "limit": 5}'
```

---

## 预防措施

### 1. 版本发布前检查清单

- [ ] 确认 docker-compose.yml 中 web 和 worker 的 volumes 配置一致
- [ ] 确认 `./runtime` 目录挂载正确，包含 uploads 子目录
- [ ] 确认 Qdrant 服务正常运行且可访问
- [ ] 确认 Celery worker 容器正常启动
- [ ] 检查 Redis 队列配置正确

### 2. 监控告警配置

- [ ] 监控 Celery worker 进程状态
- [ ] 监控文档处理队列长度
- [ ] 监控 PROCESSING 状态文档的停留时间
- [ ] 监控 Qdrant 服务健康状态
- [ ] 配置文档处理失败告警

### 3. 文档处理最佳实践

- [ ] 上传文档后等待处理完成再进行检索
- [ ] 定期检查 PROCESSING 状态文档，及时清理僵尸任务
- [ ] 向量存储失败时，文档状态应正确标记为 FAILED
- [ ] 保留详细的错误日志，便于问题排查

---

## 快速修复指南

### 场景 1：所有文档处理失败

**症状**：前端显示所有文档处理失败

**快速修复**：
```bash
# 1. 检查 worker 是否能访问上传文件
docker exec <worker> ls -la /app/runtime/uploads/

# 2. 如果目录为空或不存在，修复 docker-compose 配置
# 参考上方"正确配置"部分

# 3. 重启服务
cd enterprise-rag-v2 && docker compose up -d --force-recreate
```

### 场景 2：文档卡在 PROCESSING 状态

**症状**：文档进度停留在某个阶段不再继续

**快速修复**：
```bash
# 1. 查看卡住的文档
curl http://localhost:8000/api/v1/documents/?status=processing

# 2. 重新触发处理
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/reindex"

# 3. 或删除后重新上传
```

### 场景 3：文档已完成但检索不到

**症状**：文档状态为 COMPLETED，segment_count > 0，但检索无结果

**快速修复**：
```bash
# 1. 检查 Qdrant 集合中是否有向量数据
curl http://localhost:6333/collections

# 2. 如果 indexed_vectors_count = 0，说明向量存储失败
# 需要删除文档后重新上传
```

---

## 相关代码位置

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | 容器配置，包含 volumes 挂载 |
| `services/impl/document_service.py` | 文档处理服务，包含向量存储逻辑 |
| `infrastructure/queue/celery_app.py` | Celery worker 配置 |
| `infrastructure/queue/document_tasks.py` | 文档处理 Celery 任务 |
| `core/rag/vector_store.py` | Qdrant 向量存储操作 |
| `core/rag/collection_manager.py` | Qdrant 集合管理 |

---

## 版本记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-22 | v1.0 | 初始版本，记录文档分段向量化问题排查经验 |

---

## 联系支持

如遇类似问题无法解决，请联系技术支持团队：
- 提供完整的错误日志
- 提供数据库文档状态查询结果
- 提供 docker-compose 配置信息
