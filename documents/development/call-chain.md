# 模块调用关系文档

## 核心业务流程调用链

### 0. AI 工作台素材导入流程

```text
POST /api/v1/assets
    ↓ API 参数校验、JWT 和租户/工作空间权限
AssetService.create_asset()
    ↓ 记录 Asset 元数据，可选绑定 Dataset
POST /api/v1/assets/{id}/upload 或 /ingest
    ↓ 文件大小校验 / SafeFetcher SSRF 校验
AssetIngestionService
    ↓ LocalAssetStorage/S3 端口写入原始内容并计算 SHA-256
    ↓ 若绑定 Dataset，创建唯一 legacy Document
Celery asset.ingest_url / document.process
    ↓ DocumentProcessor 提取文本、分块
    ↓ EmbeddingService 生成向量
    ↓ Qdrant 按 workspace 写入
    ↓ 更新 Asset/Document 状态、失败原因和处理进度
```

约束：API 不直接操作 ORM；外部 URL 只能经 `SafeFetcher`；任务只传资源 ID、租户 ID 和幂等信息；素材、文档和向量必须能通过 `asset_id`/`legacy_document_id` 追溯。

### 1. 用户登录流程

```
POST /api/v1/auth/login
    ↓
[API Layer] AuthRouter.login()
    ↓ 参数验证
[Service Layer] AuthService.authenticate()
    ↓ 查询用户
[Infrastructure] UserRepository.get_by_email()
    ↓ 数据库查询
[PostgreSQL] SELECT * FROM users WHERE email = ?
    ↓ 返回用户
[Service Layer] AuthService.verify_password()
    ↓ 密码验证
[Core Layer] PasswordHasher.verify()
    ↓ 生成Token
[Service Layer] AuthService.create_tokens()
    ↓ 缓存Token
[Infrastructure] RedisCache.set()
    ↓ 记录日志
[Infrastructure] StructuredLogger.info()
    ↓ 返回响应
[API Layer] TokenResponse
```

### 2. 文档上传流程

```
POST /api/v1/documents/upload
    ↓
[API Layer] DocumentRouter.upload()
    ↓ 文件验证
[API Layer] validate_file_type()
    ↓ 保存文件
[Infrastructure] FileStorage.save()
    ↓ 创建文档记录
[Service Layer] DocumentService.create()
    ↓ 数据库插入
[Infrastructure] DocumentRepository.create()
    ↓ 触发异步任务
[Infrastructure] CeleryQueue.publish()
    ↓ 返回任务ID
[API Layer] UploadResponse

--- 异步处理 ---

[Infrastructure] Celery Worker 接收任务
    ↓
[Service Layer] DocumentService.process_document()
    ↓ 提取文本
[Core Layer] DocumentExtractor.extract()
    ↓ 清洗文本
[Core Layer] TextCleaner.clean()
    ↓ 文本分块
[Core Layer] TextSplitter.split()
    ↓ 向量化
[Core Layer] EmbeddingService.embed_batch()
    ↓ 存储向量
[Infrastructure] QdrantClient.upsert()
    ↓ 更新状态
[Infrastructure] DocumentRepository.update_status()
    ↓ 记录日志
[Infrastructure] StructuredLogger.info()
```

### 3. RAG问答流程

```
POST /api/v1/chat/query
    ↓
[API Layer] ChatRouter.query()
    ↓ 权限检查
[Service Layer] check_workspace_permission()
    ↓ 查询向量
[Service Layer] ChatService.query()
    ↓ 生成Query向量
[Core Layer] EmbeddingService.embed()
    ↓ 检索文档
[Core Layer] RAGEngine.retrieve()
    ↓ 向量检索
[Infrastructure] QdrantClient.search()
    ↓ 重排序
[Core Layer] Reranker.rerank()
    ↓ 构建Prompt
[Core Layer] PromptBuilder.build()
    ↓ 调用LLM
[Infrastructure] LLMProvider.generate()
    ↓ 流式返回
[API Layer] StreamingResponse
    ↓ 保存对话
[Infrastructure] ConversationRepository.create()
    ↓ 记录日志
[Infrastructure] StructuredLogger.info()
```

### 4. 租户创建流程

```
POST /api/v1/tenants
    ↓
[API Layer] TenantRouter.create()
    ↓ 权限检查（管理员）
[Service Layer] check_admin_permission()
    ↓ 开始事务
[Infrastructure] DatabaseSession.begin()
    ↓ 创建租户
[Service Layer] TenantService.create()
    ↓ 插入租户
[Infrastructure] TenantRepository.create()
    ↓ 创建默认工作空间
[Service Layer] WorkspaceService.create_default()
    ↓ 插入工作空间
[Infrastructure] WorkspaceRepository.create()
    ↓ 添加所有者成员
[Infrastructure] MembershipRepository.create()
    ↓ 提交事务
[Infrastructure] DatabaseSession.commit()
    ↓ 清除缓存
[Infrastructure] RedisCache.delete_pattern()
    ↓ 记录审计日志
[Infrastructure] AuditLogRepository.create()
    ↓ 返回响应
[API Layer] TenantResponse
```

---

## 跨层调用规则

### 1. API Layer → Service Layer

**调用方式**: 直接调用
```python
# API Layer
@router.post("/datasets")
async def create_dataset(
    request: DatasetCreate,
    service: DatasetService = Depends(get_dataset_service)
):
    return await service.create(request)
```

### 2. Service Layer → Core Layer

**调用方式**: 直接调用（纯函数）
```python
# Service Layer
async def process_document(self, document_id: str):
    # 调用Core Layer
    text = await self.extractor.extract(file_path)
    chunks = self.splitter.split(text)
    vectors = await self.embedder.embed_batch(chunks)
```

### 3. Service Layer → Infrastructure Layer

**调用方式**: 通过接口调用
```python
# Service Layer
async def get_dataset(self, dataset_id: str):
    # 通过Repository接口
    dataset = await self.dataset_repo.get_by_id(dataset_id)
    
    # 通过Cache接口
    cached = await self.cache.get(f"dataset:{dataset_id}")
```

### 4. 异步任务调用

**调用方式**: 消息队列
```python
# Service Layer
async def trigger_indexing(self, document_id: str):
    # 发布异步任务
    task = await self.queue.create_task(
        "index_document",
        {"document_id": document_id}
    )
    return task.id

# Infrastructure Layer (Celery Worker)
@celery_app.task
def index_document(document_id: str):
    # 执行索引任务
    service = get_document_service()
    service.process_document(document_id)
```

---

## 错误处理调用链

### 异常传播路径

```
[Infrastructure] DatabaseError
    ↓ 捕获并转换
[Service Layer] ServiceError
    ↓ 捕获并转换
[API Layer] HTTPException
    ↓ 中间件处理
[API Layer] ErrorResponse
```

### 示例

```python
# Infrastructure Layer
class DocumentRepository:
    async def get_by_id(self, id: str):
        try:
            result = await self.session.execute(query)
        except SQLAlchemyError as e:
            raise RepositoryError(f"Database error: {e}")

# Service Layer
class DocumentService:
    async def get_document(self, id: str):
        try:
            doc = await self.repo.get_by_id(id)
            if not doc:
                raise DocumentNotFoundError(id)
            return doc
        except RepositoryError as e:
            raise ServiceError(f"Failed to get document: {e}")

# API Layer
@router.get("/documents/{id}")
async def get_document(id: str, service: DocumentService = Depends()):
    try:
        doc = await service.get_document(id)
        return DocumentResponse.from_entity(doc)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 并发调用模式

### 1. 异步并发

```python
# Service Layer
async def get_dataset_with_stats(self, dataset_id: str):
    # 并发执行多个查询
    dataset, doc_count, total_size = await asyncio.gather(
        self.dataset_repo.get_by_id(dataset_id),
        self.document_repo.count_by_dataset(dataset_id),
        self.document_repo.sum_size_by_dataset(dataset_id)
    )
    return DatasetWithStats(dataset, doc_count, total_size)
```

### 2. 批量处理

```python
# Core Layer
async def embed_documents(self, documents: List[str]):
    # 分批处理
    batch_size = 32
    results = []
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        vectors = await self.embedder.embed_batch(batch)
        results.extend(vectors)
    return results
```

### 3. 缓存优先

```python
# Service Layer
async def get_dataset(self, dataset_id: str):
    # 先查缓存
    cached = await self.cache.get(f"dataset:{dataset_id}")
    if cached:
        return cached
    
    # 缓存未命中，查数据库
    dataset = await self.repo.get_by_id(dataset_id)
    
    # 写入缓存
    await self.cache.set(f"dataset:{dataset_id}", dataset, ttl=300)
    
    return dataset
```

---

## 事务边界

### Service Layer 管理事务

```python
# Service Layer
async def create_dataset_with_documents(
    self,
    dataset_data: DatasetCreate,
    documents: List[UploadFile]
):
    async with self.db_session.begin():
        # 创建数据集
        dataset = await self.dataset_repo.create(dataset_data)
        
        # 批量创建文档
        for doc in documents:
            await self.document_repo.create({
                "dataset_id": dataset.id,
                "name": doc.filename
            })
        
        # 事务自动提交
    
    # 事务外：触发异步任务
    for doc in documents:
        await self.queue.publish("process_document", {"id": doc.id})
```
