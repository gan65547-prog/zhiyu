# API接口定义文档

## 概述

本文档定义了企业级RAG系统的所有REST API接口，包括请求/响应格式、数据模型和错误处理规范。

## 基础规范

### 请求格式
- **协议**: HTTPS
- **Content-Type**: application/json
- **认证方式**: Bearer Token (JWT)
- **API版本**: v1 (通过URL路径 `/api/v1/`)

### 响应格式
所有API响应遵循统一格式：

```python
{
    "success": bool,           # 请求是否成功
    "message": str,            # 响应消息
    "data": Any,              # 响应数据
    "error_code": Optional[str],  # 错误代码
    "timestamp": datetime      # 响应时间戳
}
```

### 分页响应格式
```python
{
    "success": true,
    "message": "success",
    "data": [...],            # 数据列表
    "pagination": {
        "page": int,          # 当前页码
        "page_size": int,     # 每页数量
        "total": int,         # 总记录数
        "total_pages": int    # 总页数
    }
}
```

### HTTP状态码
- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证
- `403 Forbidden`: 无权限
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突
- `422 Unprocessable Entity`: 验证失败
- `500 Internal Server Error`: 服务器错误

---

## 0. AI 工作台素材接口（P0 基线）

当前版本提供统一素材层的最小元数据边界，接口已接入 JWT、租户和工作空间成员权限校验：

- `POST /api/v1/assets`：登记素材元数据；支持 `file`、`url`、`text`、`chat` 四类来源，可选绑定现有 `dataset_id`。
- `GET /api/v1/assets?workspace_id={id}`：按工作空间分页查询未删除素材。
- `GET /api/v1/assets/{id}`：查询单个素材。
- `DELETE /api/v1/assets/{id}`：软删除素材。
- `POST /api/v1/assets/{id}/ingest`：提交 URL 素材异步导入任务。
- `POST /api/v1/assets/{id}/upload`：上传文件原始内容并写入租户隔离对象存储，单文件上限 20MB。

说明：URL 导入由统一 `SafeFetcher` 和异步 worker 执行，当前完成安全抓取、哈希、对象存储登记，并在素材绑定 Dataset 时创建兼容 `documents` 记录；专用 worker 再执行文件解析、分块和向量化，完成后才将 Asset 置为 `ready`。创建后的状态为 `pending`，`legacy_document_id` 用于兼容映射。

## 1. 认证模块 (Authentication)

### 1.1 用户注册
**接口**: `POST /api/v1/auth/register`

**请求体**:
```python
{
    "username": str,          # 用户名 (3-50字符)
    "email": str,             # 邮箱
    "password": str,          # 密码 (8-128字符)
    "tenant_id": Optional[str]  # 租户ID (可选)
}
```

**响应**:
```python
{
    "success": true,
    "data": {
        "id": str,
        "username": str,
        "email": str,
        "tenant_id": str,
        "created_at": datetime
    }
}
```

### 1.2 用户登录
**接口**: `POST /api/v1/auth/login`

**请求体**:
```python
{
    "username": str,          # 用户名或邮箱
    "password": str           # 密码
}
```

**响应**:
```python
{
    "success": true,
    "data": {
        "access_token": str,
        "refresh_token": str,
        "token_type": "bearer",
        "expires_in": int,     # 过期时间(秒)
        "user": {
            "id": str,
            "username": str,
            "email": str,
            "tenant_id": str
        }
    }
}
```

### 1.3 刷新Token
**接口**: `POST /api/v1/auth/refresh`

**请求体**:
```python
{
    "refresh_token": str
}
```

### 1.4 用户登出
**接口**: `POST /api/v1/auth/logout`

**Headers**: `Authorization: Bearer {access_token}`

---

## 2. 租户管理模块 (Tenant Management)

### 2.1 创建租户
**接口**: `POST /api/v1/tenants`

**请求体**:
```python
{
    "name": str,              # 租户名称 (1-100字符)
    "contact_email": str,     # 联系邮箱
    "contact_phone": Optional[str],  # 联系电话
    "plan": str,              # 订阅计划: free/basic/pro/enterprise
    "metadata": Optional[dict]  # 元数据
}
```

**响应**:
```python
{
    "success": true,
    "data": {
        "id": str,
        "name": str,
        "contact_email": str,
        "plan": str,
        "status": str,        # active/suspended/deleted
        "quota": {
            "max_workspaces": int,
            "max_users": int,
            "max_datasets": int,
            "max_documents": int,
            "max_storage_gb": int,
            "max_api_calls_per_day": int
        },
        "usage": {
            "workspace_count": int,
            "user_count": int,
            "dataset_count": int,
            "document_count": int,
            "storage_used_gb": float,
            "api_calls_today": int
        },
        "created_at": datetime
    }
}
```

### 2.2 获取租户列表
**接口**: `GET /api/v1/tenants`

**查询参数**:
- `status`: 租户状态 (active/suspended/deleted)
- `plan`: 订阅计划
- `keyword`: 关键词搜索
- `page`: 页码 (默认1)
- `page_size`: 每页数量 (默认20, 最大100)

### 2.3 获取租户详情
**接口**: `GET /api/v1/tenants/{tenant_id}`

### 2.4 更新租户
**接口**: `PUT /api/v1/tenants/{tenant_id}`

### 2.5 删除租户
**接口**: `DELETE /api/v1/tenants/{tenant_id}`

---

## 3. 工作空间模块 (Workspace)

### 3.1 创建工作空间
**接口**: `POST /api/v1/workspaces`

**请求体**:
```python
{
    "name": str,              # 工作空间名称 (1-100字符)
    "description": Optional[str],  # 描述 (最大500字符)
    "metadata": Optional[dict]
}
```

**响应**:
```python
{
    "success": true,
    "data": {
        "id": str,
        "tenant_id": str,
        "name": str,
        "description": str,
        "member_count": int,
        "dataset_count": int,
        "created_at": datetime
    }
}
```

### 3.2 获取工作空间列表
**接口**: `GET /api/v1/workspaces`

### 3.3 添加工作空间成员
**接口**: `POST /api/v1/workspaces/{workspace_id}/members`

**请求体**:
```python
{
    "user_id": str,
    "role": str               # owner/admin/member/viewer
}
```

### 3.4 移除工作空间成员
**接口**: `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`

---

## 4. 数据集模块 (Dataset)

### 4.1 创建数据集
**接口**: `POST /api/v1/datasets`

**请求体**:
```python
{
    "name": str,              # 数据集名称 (1-100字符)
    "description": Optional[str],
    "workspace_id": str,
    "embedding_model": str,   # 嵌入模型名称
    "chunk_size": int,        # 分块大小 (默认500)
    "chunk_overlap": int,     # 分块重叠 (默认50)
    "metadata": Optional[dict]
}
```

**响应**:
```python
{
    "success": true,
    "data": {
        "id": str,
        "name": str,
        "workspace_id": str,
        "embedding_model": str,
        "document_count": int,
        "total_chunks": int,
        "created_at": datetime
    }
}
```

### 4.2 获取数据集列表
**接口**: `GET /api/v1/datasets`

**查询参数**:
- `workspace_id`: 工作空间ID
- `keyword`: 关键词搜索
- `page`: 页码
- `page_size`: 每页数量

### 4.3 获取数据集详情
**接口**: `GET /api/v1/datasets/{dataset_id}`

### 4.4 更新数据集
**接口**: `PUT /api/v1/datasets/{dataset_id}`

### 4.5 删除数据集
**接口**: `DELETE /api/v1/datasets/{dataset_id}`

---

## 5. 文档管理模块 (Document)

### 5.1 上传文档
**接口**: `POST /api/v1/documents/upload`

**Content-Type**: `multipart/form-data`

**表单字段**:
- `file`: 文件 (必需)
- `dataset_id`: 数据集ID (必需)
- `tags`: 标签列表 (可选, JSON数组)
- `metadata`: 元数据 (可选, JSON对象)

**响应**:
```python
{
    "success": true,
    "data": {
        "id": str,
        "dataset_id": str,
        "file_name": str,
        "file_type": str,     # pdf/docx/txt/md/html
        "file_size": int,     # 字节
        "status": str,        # pending/processing/completed/failed
        "tags": List[str],
        "chunk_count": int,
        "created_at": datetime
    }
}
```

### 5.2 获取文档列表
**接口**: `GET /api/v1/documents`

**查询参数**:
- `dataset_id`: 数据集ID
- `status`: 文档状态
- `file_type`: 文件类型
- `tags`: 标签 (逗号分隔)
- `keyword`: 关键词搜索
- `page`: 页码
- `page_size`: 每页数量

### 5.3 获取文档详情
**接口**: `GET /api/v1/documents/{document_id}`

### 5.4 更新文档
**接口**: `PUT /api/v1/documents/{document_id}`

**请求体**:
```python
{
    "file_name": Optional[str],
    "tags": Optional[List[str]],
    "metadata": Optional[dict]
}
```

### 5.5 删除文档
**接口**: `DELETE /api/v1/documents/{document_id}`

### 5.6 批量删除文档
**接口**: `POST /api/v1/documents/batch-delete`

**请求体**:
```python
{
    "document_ids": List[str]  # 文档ID列表 (至少1个)
}
```

### 5.7 重新索引文档
**接口**: `POST /api/v1/documents/{document_id}/reindex`

**请求体**:
```python
{
    "force": bool             # 是否强制重新索引 (默认false)
}
```

### 5.8 获取文档统计
**接口**: `GET /api/v1/documents/statistics`

**查询参数**:
- `dataset_id`: 数据集ID (可选)

**响应**:
```python
{
    "success": true,
    "data": {
        "total_count": int,
        "pending_count": int,
        "processing_count": int,
        "completed_count": int,
        "failed_count": int,
        "total_size": int,    # 总大小(字节)
        "total_chunks": int
    }
}
```

---

## 6. 对话模块 (Chat)

### 6.1 发送对话请求
**接口**: `POST /api/v1/chat`

**请求体**:
```python
{
    "dataset_id": str,
    "query": str,             # 用户查询 (1-2000字符)
    "conversation_id": Optional[str],  # 会话ID
    "history": Optional[List[dict]],   # 历史消息
    "retrieval_mode": str,    # semantic/keyword/hybrid (默认hybrid)
    "top_k": int,             # 返回top-k文档 (1-20, 默认5)
    "temperature": float,     # 生成温度 (0.0-2.0, 默认0.7)
    "max_tokens": int,        # 最大token数 (100-4000, 默认2000)
    "stream": bool            # 是否流式返回 (默认false)
}
```

**响应 (非流式)**:
```python
{
    "success": true,
    "data": {
        "conversation_id": str,
        "message_id": str,
        "answer": str,
        "retrieved_chunks": [
            {
                "chunk_id": str,
                "document_id": str,
                "document_name": str,
                "content": str,
                "score": float,
                "metadata": dict
            }
        ],
        "tokens_used": int,
        "retrieval_time_ms": int,
        "generation_time_ms": int
    }
}
```

**响应 (流式)**: Server-Sent Events (SSE)
```
data: {"conversation_id": "...", "message_id": "...", "delta": "Hello", "finish_reason": null}
data: {"conversation_id": "...", "message_id": "...", "delta": " world", "finish_reason": null}
data: {"conversation_id": "...", "message_id": "...", "delta": "", "finish_reason": "stop"}
```

### 6.2 创建会话
**接口**: `POST /api/v1/conversations`

**请求体**:
```python
{
    "dataset_id": str,
    "title": Optional[str],
    "metadata": Optional[dict]
}
```

### 6.3 获取会话列表
**接口**: `GET /api/v1/conversations`

**查询参数**:
- `dataset_id`: 数据集ID
- `keyword`: 关键词搜索
- `page`: 页码
- `page_size`: 每页数量

### 6.4 获取会话详情
**接口**: `GET /api/v1/conversations/{conversation_id}`

### 6.5 获取会话消息历史
**接口**: `GET /api/v1/conversations/{conversation_id}/messages`

**响应**:
```python
{
    "success": true,
    "data": [
        {
            "id": str,
            "conversation_id": str,
            "role": str,      # user/assistant/system
            "content": str,
            "retrieved_chunks": Optional[List[dict]],
            "tokens_used": Optional[int],
            "created_at": datetime
        }
    ]
}
```

### 6.6 删除会话
**接口**: `DELETE /api/v1/conversations/{conversation_id}`

---

## 7. 错误代码

| 错误代码 | 说明 |
|---------|------|
| `AUTH_001` | 认证失败 |
| `AUTH_002` | Token过期 |
| `AUTH_003` | Token无效 |
| `AUTH_004` | 权限不足 |
| `TENANT_001` | 租户不存在 |
| `TENANT_002` | 租户已暂停 |
| `TENANT_003` | 超出配额限制 |
| `WORKSPACE_001` | 工作空间不存在 |
| `WORKSPACE_002` | 无工作空间权限 |
| `DATASET_001` | 数据集不存在 |
| `DATASET_002` | 数据集名称重复 |
| `DOCUMENT_001` | 文档不存在 |
| `DOCUMENT_002` | 文件类型不支持 |
| `DOCUMENT_003` | 文件大小超限 |
| `DOCUMENT_004` | 文档处理失败 |
| `CHAT_001` | 会话不存在 |
| `CHAT_002` | 查询内容为空 |
| `CHAT_003` | LLM调用失败 |
| `SYSTEM_001` | 系统内部错误 |
| `SYSTEM_002` | 数据库错误 |
| `SYSTEM_003` | 缓存错误 |

---

## 8. 认证和授权

### 8.1 JWT Token结构
```python
{
    "sub": str,               # 用户ID
    "username": str,
    "tenant_id": str,
    "exp": int,               # 过期时间戳
    "iat": int,               # 签发时间戳
    "type": str               # access/refresh
}
```

### 8.2 权限级别
- **系统管理员**: 所有权限
- **租户所有者**: 租户内所有权限
- **工作空间管理员**: 工作空间内所有权限
- **工作空间成员**: 读写权限
- **工作空间查看者**: 只读权限

---

## 9. 速率限制

| 用户类型 | 限制 |
|---------|------|
| 免费版 | 100请求/小时 |
| 基础版 | 1000请求/小时 |
| 专业版 | 10000请求/小时 |
| 企业版 | 无限制 |

**响应头**:
- `X-RateLimit-Limit`: 限制数量
- `X-RateLimit-Remaining`: 剩余数量
- `X-RateLimit-Reset`: 重置时间戳

---

## 10. API版本控制

- 当前版本: `v1`
- 版本通过URL路径指定: `/api/v1/`
- 向后兼容至少保持6个月
- 废弃的API会提前3个月通知
