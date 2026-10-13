# 架构总览

> 基于实际代码 `enterprise-rag-v2/main.py` 和 `core/config.py` 生成
> 最后更新: 2026-04-05

## 系统整体架构

### 四层架构设计

```
┌───────────────────────┐
│      API Layer       │  ← RESTful接口、请求验证、错误处理
├───────────────────────┤
│    Service Layer     │  ← 业务逻辑、事务管理、服务编排
├───────────────────────┤
│     Core Layer       │  ← 核心算法、领域模型、业务规则
├───────────────────────┤
│ Infrastructure Layer │  ← 数据持久化、外部服务、配置管理
└───────────────────────┘
```

### 技术栈

| 类别 | 技术 | 版本/说明 |
|------|------|----------|
| **后端框架** | FastAPI | Python 3.10+ |
| **前端框架** | Vue 3 + TypeScript | Vite 构建 |
| **状态管理** | Pinia | Vue 3 官方推荐 |
| **UI 组件库** | Ant Design Vue | 企业级组件库 |
| **数据库** | PostgreSQL / SQLite | 生产用 PostgreSQL，开发可用 SQLite |
| **ORM** | SQLAlchemy (异步) | AsyncSession + asyncpg |
| **向量存储** | Qdrant | HTTP 接口，端口 6333 |
| **缓存** | Redis | 会话缓存、角色缓存 |
| **任务队列** | Celery | Redis 作为 Broker (非 RabbitMQ) |
| **认证方式** | JWT + OAuth2 | 支持密码登录和第三方登录(GitHub) |
| **LLM 集成** | OpenAI / DeepSeek / 智谱 GLM | 可配置多 Provider |
| **嵌入模型** | BGE 系列 | bge-small-zh-v1.5 等 |
| **文档解析** | PyPDF, python-docx, BeautifulSoup | 支持 PDF/TXT/MD/HTML/DOCX/EPUB |
| **容器化** | Docker Compose | 开发和生产部署 |

### 设计原则

1. **分层架构**: 清晰的职责分离，API → Service → Core → Infrastructure
2. **依赖倒置**: 高层模块不依赖低层模块，依赖抽象接口
3. **接口隔离**: 客户端只依赖必要的接口定义
4. **单一职责**: 每个模块只负责一个功能
5. **开闭原则**: 对扩展开放，对修改封闭

## 核心组件

### API Layer (`api/`)
- **路由注册** (`api/routers/`): auth, tenants, workspaces, datasets, documents, chat, oauth, backups, webhooks, users
- **中间件** (`api/middleware/`): CORS, Rate Limiting, Error Handling, Request Logging
- **数据模型** (`api/schemas/`): Pydantic 请求/响应模型
- **前缀规范**: 所有API使用 `/api/v1/` 前缀

### Service Layer (`services/`)
- **接口定义** (`services/interfaces/`): 抽象接口契约
- **实现层** (`services/impl/`): 具体业务逻辑实现
- **核心服务**:
  - `auth_service`: 认证与授权
  - `tenant_service`: 租户管理
  - `workspace_service`: 工作空间管理
  - `dataset_service`: 数据集(知识库)管理
  - `document_service`: 文档上传与处理
  - `chat_service`: RAG 对话
  - `rag_service`: 向量检索与生成

### Core Layer (`core/`)
- **配置管理** (`core/config.py`): Pydantic Settings 环境变量配置
- **接口定义** (`core/interfaces/`): 核心抽象接口
- **安全工具** (`core/security/`): JWT 编解码、密码哈希

### Infrastructure Layer (`infrastructure/`)
- **数据库** (`infrastructure/database/`):
  - `models.py`: SQLAlchemy ORM 模型（15张表）
  - `session.py`: 异步会话工厂
  - `migrations/`: Alembic 迁移脚本
- **缓存** (`infrastructure/cache/`): Redis 缓存封装
- **存储** (`infrastructure/storage/`): 本地/S3 文件存储
- **监控** (`infrastructure/monitoring/`): 健康检查、指标收集

## 已注册的 API 路由

从 `main.py` 中提取的实际路由:

| 路由前缀 | 模块 | 说明 |
|---------|------|------|
| `/api/v1/auth` | auth_router | 登录、注册、Token刷新、当前用户 |
| `/api/v1/tenants` | tenants_router | 租户CRUD |
| `/api/v1/workspaces` | workspaces_router | 工作空间CRUD、成员管理 |
| `/api/v1/datasets` | datasets_router | 数据集(知识库)CRUD |
| `/api/v1/documents` | documents_router | 文档上传、删除、列表 |
| `/api/v1/chat` | chat_router | 对话创建、消息获取、流式响应 |
| `/api/v1/oauth` | oauth_router | GitHub OAuth登录 |
| `/api/v1/backups` | backup_router | 备份恢复 |
| `/api/v1/webhooks` | webhooks_router | Webhook 回调 |
| `/api/v1/users` | users_router | 用户管理 |

## 部署架构

### 当前支持
- **容器化**: Docker Compose（开发/生产）
- **监控**: Prometheus + Grafana
- **日志**: 结构化日志 (Python logging)
- **健康检查**: `/health` 端点
- **指标收集**: `/metrics` 端点

### Docker Compose 服务
```
services:
  postgres    # PostgreSQL 数据库
  redis       # Redis 缓存 + Celery Broker
  qdrant      # Qdrant 向量数据库
  api         # FastAPI 后端服务
  celery-worker  # Celery 异步任务Worker
  frontend    # Vue 3 前端 (可选)
```

## 安全架构

- **认证授权**: JWT + RBAC (基于角色的访问控制)
- **多租户隔离**: 数据库级租户ID隔离
- **工作空间权限**: owner/admin/member/viewer 四级角色
- **数据加密**: 密码 bcrypt 哈希、API密钥加密存储
- **审计日志**: 全操作记录 (audit_logs 表)
- **防护措施**: CORS、Rate Limiting、CSRF、XSS、SQL注入防护
- **OAuth集成**: 支持 GitHub 第三方登录

## 扩展性考虑

- **水平扩展**: API 无状态设计，支持多实例部署
- **模块化设计**: 服务通过接口解耦，可独立替换
- **API版本控制**: `/api/v1/` 前缀，预留版本升级空间
- **LLM Provider切换**: 通过环境变量配置不同 LLM 提供商
- **嵌入模型可换**: 数据集级别配置不同的嵌入模型
