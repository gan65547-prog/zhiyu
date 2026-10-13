# 模块职责说明文档

## 1. API Layer (API层)

### 职责
- **HTTP请求处理**: 接收和解析HTTP请求
- **参数验证**: 使用Pydantic进行请求参数验证
- **响应格式化**: 统一的响应格式（成功/失败）
- **错误处理**: 捕获异常并转换为HTTP错误响应
- **中间件管理**: 认证、日志、CORS等中间件

### 不负责
- ❌ 业务逻辑实现
- ❌ 数据库直接访问
- ❌ 复杂的数据处理

### 依赖
- 仅依赖 Service Layer 的接口

### 关键组件
- `routers/`: 路由定义
- `middleware/`: 中间件
- `schemas/`: 请求/响应模型
- `dependencies.py`: 依赖注入

---

## 2. Service Layer (服务层)

### 职责
- **业务逻辑编排**: 协调多个Core组件完成业务流程
- **事务管理**: 管理数据库事务边界
- **权限检查**: 验证用户权限和资源访问权限
- **数据转换**: Entity ↔ DTO 转换
- **业务规则验证**: 复杂的业务规则校验

### 不负责
- ❌ HTTP协议处理
- ❌ 具体的算法实现
- ❌ 直接的数据库操作

### 依赖
- Core Layer 的接口
- Infrastructure Layer 的抽象接口

### 关键组件
- `auth_service.py`: 认证授权服务
- `tenant_service.py`: 租户管理服务
- `dataset_service.py`: 知识库服务
- `document_service.py`: 文档服务
- `chat_service.py`: 聊天服务

---

## 3. Core Layer (核心层)

### 职责
- **领域逻辑**: 纯业务逻辑实现
- **RAG引擎**: 检索增强生成算法
- **文档处理**: 文档解析、分块、向量化
- **业务实体**: 领域模型定义
- **业务规则**: 核心业务规则

### 不负责
- ❌ 数据持久化
- ❌ 外部服务调用
- ❌ HTTP处理

### 依赖
- 无外部依赖（纯业务逻辑）

### 关键组件
- `rag/`: RAG引擎
  - `retriever.py`: 文档检索
  - `reranker.py`: 结果重排序
  - `generator.py`: 答案生成
- `document_processor/`: 文档处理
  - `extractors/`: 文档提取器
  - `splitters/`: 文本分割器
  - `cleaners/`: 文本清洗
- `embedding/`: 向量化服务
- `entities/`: 业务实体
- `interfaces/`: 抽象接口定义

---

## 4. Infrastructure Layer (基础设施层)

### 职责
- **数据持久化**: 数据库操作实现
- **缓存管理**: Redis缓存实现
- **消息队列**: Celery任务队列
- **文件存储**: 文件上传下载
- **外部服务**: 第三方API调用（飞书、企业微信）
- **监控日志**: 日志收集、指标上报

### 不负责
- ❌ 业务逻辑
- ❌ 业务规则验证

### 依赖
- 外部系统和第三方服务

### 关键组件
- `database/`: 数据库实现
  - `repositories/`: Repository实现
  - `models.py`: SQLAlchemy模型
  - `session.py`: 数据库会话管理
- `cache/`: 缓存实现
  - `redis_cache.py`: Redis缓存
- `queue/`: 消息队列
  - `celery_app.py`: Celery应用
  - `tasks/`: 异步任务
- `storage/`: 文件存储
  - `local_storage.py`: 本地存储
  - `s3_storage.py`: S3存储
- `external/`: 外部服务
  - `feishu/`: 飞书集成
  - `wecom/`: 企业微信集成
- `monitoring/`: 监控
  - `logger.py`: 日志实现
  - `metrics.py`: 指标收集

---

## 模块调用规则

### 依赖方向（单向依赖）
```
API Layer → Service Layer → Core Layer
                ↓              ↑
         Infrastructure Layer (通过接口)
```

### 禁止的依赖
- ❌ Core Layer 不能依赖 Infrastructure Layer
- ❌ Service Layer 不能依赖 API Layer
- ❌ 同层之间避免循环依赖

### 通信方式
- **同步调用**: API → Service → Core
- **异步任务**: Service → Infrastructure (Celery)
- **事件驱动**: 使用消息队列解耦

---

## 数据流向

### 请求流
```
HTTP Request
    ↓
API Layer (验证)
    ↓
Service Layer (业务逻辑)
    ↓
Core Layer (领域逻辑)
    ↓
Infrastructure Layer (数据存储)
```

### 响应流
```
Infrastructure Layer (数据查询)
    ↓
Core Layer (业务处理)
    ↓
Service Layer (数据转换)
    ↓
API Layer (响应格式化)
    ↓
HTTP Response
```