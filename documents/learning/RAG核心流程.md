# Enterprise RAG V2 核心业务流程

## 概述

Enterprise RAG V2 是一个完整的企业级 RAG（检索增强生成）系统，包含文档上传、清洗、切分、向量化、检索和对话查询等完整流程。

---

## 一、整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                RAG 核心业务流程                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   1. 文件上传  │ -> │   2. 文本清洗  │ -> │   3. 文本切分  │ -> │  4. 向量化   │  │
│  │  Upload API   │    │  Extraction  │    │   Splitting  │    │ Embedding    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                                                            │           │
│         v                                                            v           │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         5. Qdrant 向量存储                                │   │
│  │                    Vector Store (with Fallback)                          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│                                      v                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   6. 检索     │ -> │  7. Rerank   │ -> │ 8. LLM 生成   │ -> │  9. 流式输出  │  │
│  │  Retrieval    │    │  Reranking  │    │  Generation  │    │   Streaming  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、文档上传流程 (Document Upload)

### 2.1 API 入口

**文件**: [api/routers/documents.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/api/routers/documents.py)

```python
@router.post("/datasets/{dataset_id}")
async def upload_document_to_dataset(
    dataset_id: UUID,
    file: UploadFile = File(...),
    process_rule: str = Form(default=None),
):
    # 1. 保存文件到本地 ./uploads 目录
    # 2. 配额校验 (quota_service.assert_can_add_document)
    # 3. 调用 document_service.upload_document() 创建文档记录
    # 4. 触发 Celery 异步任务 process_document_task
```

### 2.2 核心流程

```
POST /api/v1/datasets/{dataset_id}
    │
    ├── 1. 文件读取 (分块 1MB)
    │       └── 保存到 ./uploads/{uuid}.{ext}
    │
    ├── 2. 配额检查
    │       └── tenant_id + file_size -> quota_service
    │
    ├── 3. 创建文档记录
    │       └── document_service.upload_document()
    │       └── 状态: pending -> processing -> completed/failed
    │
    └── 4. 触发异步处理
            └── process_document_task.apply_async()
            └── queue: "documents_high"
```

### 2.3 关键代码片段

```python
# 文档上传服务 (services/impl/document_service.py)
async def upload_document(
    dataset_id: UUID,
    file_path: str,
    file_name: str,
    file_type: str,
    file_size: int,
    tags=None,
    metadata=None
) -> dict:
    # 1. 创建 Document 记录
    # 2. 返回 document_id
```

---

## 三、文档清洗与提取 (Document Extraction)

### 3.1 处理器

**文件**: [core/rag/document_processor.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/document_processor.py)

### 3.2 支持的文件格式

| 格式 | 提取方法 | 依赖库 |
|------|---------|--------|
| PDF | `pypdf.PdfReader` | pypdf |
| TXT/MD | 直接读取 | 内置 |
| DOCX | `docx.Document` | python-docx |
| HTML | BeautifulSoup | bs4 |
| EPUB | ebooklib / zipfile | ebooklib |

### 3.3 提取流程

```python
class DocumentProcessor:
    async def extract_text(self, file_path: str, file_type: str) -> str:
        if file_type in ["pdf", ".pdf"]:
            return self._extract_pdf(file_path)
        elif file_type in ["txt", ".txt", "md", ".md"]:
            return self._extract_txt(file_path)
        elif file_type in ["docx", ".docx"]:
            return self._extract_docx(file_path)
        elif file_type in ["html", ".html"]:
            return self._extract_html(file_path)
        elif file_type in ["epub", ".epub"]:
            return self._extract_epub(file_path)
```

### 3.4 EPUB 特殊处理

EPUB 文件支持两种解析方式：
1. **主方案**: `ebooklib.epub.read_epub()` - 解析 HTML 内容
2. **备用方案**: `zipfile` 直接解压 - 处理编码问题

```python
def _extract_epub(self, file_path: str) -> str:
    try:
        return self._extract_epub_with_ebooklib(file_path)
    except:
        return self._extract_epub_with_zipfile(file_path)  # 备用
```

---

## 四、文本切分 (Text Splitting)

### 4.1 切分策略

**文件**: [core/rag/document_processor.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/document_processor.py#L26-L55)

```python
class RecursiveCharacterTextSplitter:
    def __init__(self, separators: Optional[List[str]] = None):
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", "，", " ", ""]

    def split(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        # 递归切分：优先在较大粒度切分，不满足时依次减小
```

### 4.2 切分参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| chunk_size | 500 | 每个 chunk 的目标字符数 |
| chunk_overlap | 50 | 相邻 chunk 之间的重叠字符数 |

### 4.3 切分算法

```
输入: "第一章\n\n这是第一段内容。\n\n这是第二段内容。"

1. 从起始位置开始，取 chunk_size 字符
2. 从后往前查找分隔符 (从 self.separators 列表选择)
3. 在分隔符位置切分
4. 下一个 chunk 从 (end - overlap) 开始
5. 重复直到文本结束
```

### 4.4 Chunk 元数据

```python
def create_chunks(
    self,
    text: str,
    document_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    # 返回格式:
    [
        {
            "id": f"{document_id}_chunk_0",
            "document_id": "xxx",
            "chunk_index": 0,
            "content": "chunk文本内容",
            "metadata": {}
        },
        ...
    ]
```

---

## 五、向量化 (Embedding)

### 5.1 Embedding 服务

**文件**: [core/rag/embedding.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/embedding.py)

### 5.2 支持的模型

| 模型 | 向量维度 | 说明 |
|------|---------|------|
| BGE-small-zh-v1.5 | 512 | **默认模型**，性能优秀 |
| BGE-large-zh-v1.5 | 1024 | 更高精度，需要更多资源 |
| Ollama (nomic-embed-text) | 768 | 本地部署 |
| DeepSeek | 512 | 使用 BGE 模型替代 |

### 5.3 模型加载策略

```python
def _resolve_model_name(self) -> str:
    # 优先级:
    # 1. /app/shared/models/bge-small-zh-v1.5 (本地镜像)
    # 2. EMBEDDING_MODEL_PATH 配置路径
    # 3. /opt/models/bge-small-zh-v1.5
    # 4. BAAI/bge-small-zh-v1.5 (HuggingFace)
```

### 5.4 批量向量化

```python
class SentenceTransformerEmbedding:
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # 使用 run_in_executor 在线程池中执行
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True).tolist()
        )
        return embeddings
```

### 5.5 获取服务实例

```python
def get_embedding_service(model_name: Optional[str] = None) -> EmbeddingService:
    if "bge-small" in model_name_lower:
        return BGESmallZhEmbedding()
    elif "bge-large" in model_name_lower:
        return BGELargeZhEmbedding()
    elif "nomic" in model_name_lower:
        return OllamaEmbedding(model_name)
    else:
        return SentenceTransformerEmbedding(model_name)
```

---

## 六、向量存储 (Vector Store)

### 6.1 向量存储实现

**文件**: [core/rag/vector_store.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/vector_store.py)

### 6.2 存储后端优先级

```python
async def create_vector_store(...) -> VectorStore:
    # 1. QdrantVectorStore (HTTP 连接 Docker Qdrant) - 多进程共享
    # 2. EmbeddedQdrantStore (本地文件) - 单进程独占
    # 3. MemoryVectorStore (内存) - 最后兜底
```

### 6.3 Collection 命名策略

```python
class CollectionManager:
    @staticmethod
    def get_workspace_collection_name(workspace_id: str) -> str:
        return f"rag_workspace_{workspace_id}"
```

### 6.4 向量插入 (Upsert)

```python
async def upsert(self, points: List[Dict[str, Any]], wait: bool = True) -> bool:
    # points 格式:
    # [
    #     {
    #         "id": "uuid",
    #         "vector": [0.1, 0.2, ...],
    #         "payload": {
    #             "document_id": "xxx",
    #             "document_name": "文件名.pdf",
    #             "dataset_id": "xxx",
    #             "chunk_index": 0,
    #             "content": "文本内容",
    #             "workspace_id": "xxx"
    #         }
    #     }
    # ]
```

---

## 七、检索流程 (Retrieval)

### 7.1 RAG 引擎

**文件**: [core/rag/rag_engine.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/rag_engine.py)

### 7.2 检索模式

| 模式 | 说明 |
|------|------|
| semantic | 语义向量检索 (默认) |
| keyword | 关键词检索 |
| hybrid | 语义 + 关键词混合 |

### 7.3 检索流程

```python
async def retrieve(self, query: str, context: QueryContext) -> List[RetrievedDocument]:
    if context.retrieval_mode == "semantic":
        return await self.semantic_search(query, context)
    elif context.retrieval_mode == "keyword":
        return await self.keyword_search(query, context)
    else:
        # hybrid 模式
        semantic_results = await self.semantic_search(query, context)
        keyword_results = await self.keyword_search(query, context)
        return self._merge_results(semantic_results, keyword_results)
```

### 7.4 语义检索流程

```python
async def semantic_search(self, query: str, context: QueryContext) -> List[RetrievedDocument]:
    # 1. 查询文本向量化
    query_vector = await self.embedding_service.embed_text(query)

    # 2. 构建过滤器 (按 workspace_id 和 dataset_id)
    filters = {"dataset_id": {"$in": dataset_id_strs}}

    # 3. 向量相似度搜索
    results = await self.vector_store.search(
        query_vector=query_vector,
        top_k=context.top_k * 2,  # 预留 rerank 空间
        score_threshold=context.similarity_threshold,
        filters=filters
    )

    # 4. Rerank (可选)
    if context.rerank and len(results) > 1:
        documents = await self.reranker.rerank(query, documents, context.top_k)

    return documents[:context.top_k]
```

### 7.5 Fallback 机制

```python
try:
    results = await self.vector_store.search(...)
except (RuntimeError, ValueError, TypeError, AttributeError):
    # Qdrant 不可用时切换到内存向量存储
    from core.rag.vector_store import MemoryVectorStore
    self.vector_store = MemoryVectorStore(...)
    results = await self.vector_store.search(...)
```

---

## 八、Rerank 重排序

### 8.1 Reranker 实现

**文件**: [core/rag/reranker.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/reranker.py)

### 8.2 两种模式

| 模式 | 说明 |
|------|------|
| DocumentReranker | 调用远程 rerank API (`/api/rerank`) |
| SimpleReranker | 基于关键词重叠的简单重排序 |

### 8.3 SimpleReranker 算法

```python
async def rerank(self, query: str, documents: List[RetrievedDocument], top_k=None):
    query_terms = set(query.lower().split())

    for doc in documents:
        content_terms = set(doc.content.lower().split())
        overlap = len(query_terms & content_terms)
        # 关键词重叠加分
        doc.score = doc.score * (1 + overlap * 0.1)

    documents.sort(key=lambda d: d.score, reverse=True)
    return documents[:top_k]
```

---

## 九、对话查询 (Chat Query)

### 9.1 Chat 服务

**文件**: [services/impl/chat_service.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/services/impl/chat_service.py)

### 9.2 API 入口

**文件**: [api/routers/chat.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/api/routers/chat.py)

```python
@router.post("/")
async def chat(request: ChatRequest, ...):
    # 1. 权限校验
    await chat_service.verify_dataset_access(dataset_id, user_id, tenant_id)

    # 2. RAG 查询
    rag_response = await rag_engine.query(
        query=request.query,
        context=query_context,
        conversation_history=history,
        temperature=temperature,
        max_tokens=max_tokens
    )

    # 3. 保存消息
    await self._save_message(conversation_id, "user", query)
    await self._save_message(conversation_id, "assistant", answer)
```

### 9.3 流式响应

```python
@router.post("/stream")
async def chat_stream(request: ChatRequest, ...):
    async def generate():
        async for chunk in chat_service.chat_stream(...):
            if chunk.get("type") == "token":
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk.get("type") == "retrieval":
                yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 9.4 完整对话流程

```
POST /api/v1/chat
    │
    ├── 1. 权限校验
    │       └── verify_dataset_access(dataset_id, user_id, tenant_id)
    │
    ├── 2. 会话管理
    │       └── 创建新会话 (无 conversation_id 时)
    │
    ├── 3. 向量检索
    │       └── rag_engine.retrieve(query, context)
    │
    ├── 4. LLM 生成
    │       └── rag_engine.query() 或 query_stream()
    │
    ├── 5. 消息持久化
    │       └── _save_message(user + assistant)
    │
    └── 6. 返回响应
            └── answer + retrieved_documents + conversation_id
```

---

## 十、LLM 生成 (Response Generation)

### 10.1 LLM 提供者

**文件**: [core/rag/llm_provider.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/llm_provider.py)

### 10.2 支持的模型

| 提供者 | 模型 | 说明 |
|--------|------|------|
| Ollama | qwen2.5 / deepseek | 本地部署 |
| DeepSeek | deepseek-chat | 远程 API |

### 10.3 Prompt 构造

```python
async def generate(self, query, documents, conversation_history=None, ...):
    # 构造 system prompt
    system_prompt = """你是一个专业的助手。请根据以下参考文档回答用户的问题。
    如果参考文档中没有相关信息，请如实告知。

    参考文档:
    {documents_content}
    """

    # 构造 user prompt
    user_prompt = f"问题: {query}\n\n请根据参考文档回答。"

    # 发送请求到 LLM
```

---

## 十一、Celery 异步任务

### 11.1 文档处理任务

**文件**: [infrastructure/queue/document_tasks.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/infrastructure/queue/document_tasks.py)

```python
@celery_app.task(name="document_tasks.process_document_task")
def process_document_task(document_id: str):
    # 异步执行文档索引
    # 1. 提取文本
    # 2. 切分
    # 3. 向量化
    # 4. 存储
```

### 11.2 队列配置

| 队列名 | 用途 |
|--------|------|
| documents_high | 高优先级文档处理 |
| chat_async | 异步聊天任务 |

---

## 十二、关键数据模型

### 12.1 Document

```python
class Document(Base):
    id: UUID
    dataset_id: UUID
    file_name: str
    file_type: str
    file_path: str
    file_size: int
    status: DocumentStatus  # pending/processing/completed/failed
    chunk_count: int
    error_message: str
```

### 12.2 DocumentChunk

```python
class DocumentChunk(Base):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    metadata: dict
```

### 12.3 Conversation & Message

```python
class Conversation(Base):
    id: UUID
    dataset_id: UUID
    user_id: str
    title: str
    visibility: str  # private/workspace/tenant
    workspace_id: UUID

class Message(Base):
    id: UUID
    conversation_id: UUID
    role: str  # user/assistant
    content: str
    retrieved_chunks: list
    tokens_used: int
```

---

## 十三、核心配置

### 13.1 RAG 配置

**文件**: [core/rag_config.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag_config.py)

```python
class RAGConfig:
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_model_path: str = "/app/shared/models/bge-small-zh-v1.5"
    vector_size: int = 512
    collection_name: str = "default"
    qdrant_url: str = "http://localhost:6333"
    rerank_model: str = "bge-reranker-large"
    llm_url: str = "http://localhost:11434"
    deepseek_api_key: str = ""
```

---

## 十四、完整流程时序图

```
用户                    API                      Celery Worker              Qdrant
 │                      │                            │                        │
 │  POST /upload        │                            │                        │
 │─────────────────────>│                            │                        │
 │                      │  保存文件                   │                        │
 │                      │───────────────────────────>│                        │
 │                      │  创建 Document             │                        │
 │                      │                            │                        │
 │  201 Created          │                            │                        │
 │<─────────────────────│                            │                        │
 │                      │                            │                        │
 │                      │  process_document_task      │                        │
 │                      │───────────────────────────>│                        │
 │                      │                            │                        │
 │                      │                            │  提取文本                │
 │                      │                            │───────────────────────>│
 │                      │                            │                        │
 │                      │                            │  切分文本                │
 │                      │                            │                        │
 │                      │                            │  向量化 (BGE)           │
 │                      │                            │                        │
 │                      │                            │  upsert                 │
 │                      │                            │───────────────────────>│
 │                      │                            │                        │
 │                      │                            │  更新状态 completed      │
 │                      │                            │                        │
 │                      │                            │                        │
 │  POST /chat          │                            │                        │
 │─────────────────────>│                            │                        │
 │                      │                            │                        │
 │                      │  验证权限                   │                        │
 │                      │                            │                        │
 │                      │  查询向量                  │                        │
 │                      │────────────────────────────────────────────────────>│
 │                      │                            │                        │
 │                      │  Rerank                    │                        │
 │                      │                            │                        │
 │                      │  LLM 生成                  │                        │
 │                      │                            │                        │
 │  {answer, sources}   │                            │                        │
 │<─────────────────────│                            │                        │
```

---

## 十五、错误处理与 Fallback

### 15.1 向量存储 Fallback

```
QdrantVectorStore (Docker) → EmbeddedQdrantStore (本地文件) → MemoryVectorStore (内存)
```

### 15.2 LLM Fallback

```
DeepSeek (远程 API) → Ollama (本地)
```

### 15.3 常见错误排查

| 错误场景 | 排查方向 |
|---------|---------|
| 文档处理失败 | 检查文件路径、权限、依赖库 |
| 向量检索失败 | 检查 Qdrant 服务、collection 是否存在 |
| LLM 生成失败 | 检查 API Key、Ollama 服务 |
| 无检索结果 | 确认文档已上传且索引完成 |

---

## 十六、文件速查表

| 功能 | 文件路径 |
|------|---------|
| 文档上传 API | [api/routers/documents.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/api/routers/documents.py) |
| 文档服务 | [services/impl/document_service.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/services/impl/document_service.py) |
| 文档索引服务 | [services/impl/document_indexing_service.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/services/impl/document_indexing_service.py) |
| 文档处理器 | [core/rag/document_processor.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/document_processor.py) |
| 向量化服务 | [core/rag/embedding.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/embedding.py) |
| 向量存储 | [core/rag/vector_store.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/vector_store.py) |
| RAG 引擎 | [core/rag/rag_engine.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/rag_engine.py) |
| Reranker | [core/rag/reranker.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/reranker.py) |
| LLM 提供者 | [core/rag/llm_provider.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag/llm_provider.py) |
| Chat API | [api/routers/chat.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/api/routers/chat.py) |
| Chat 服务 | [services/impl/chat_service.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/services/impl/chat_service.py) |
| 异步任务 | [infrastructure/queue/document_tasks.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/infrastructure/queue/document_tasks.py) |
| RAG 配置 | [core/rag_config.py](file:///Volumes/TOSHIBA/AIAgent/ganfy/enterprise-rag-v2/core/rag_config.py) |