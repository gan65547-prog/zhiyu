# 企业级 RAG 系统 V2

基于生产级架构重构的企业级 AI 知识库系统。

## 架构概述

采用四层架构设计：
- **API Layer**: HTTP请求处理、参数验证、响应格式化
- **Service Layer**: 业务逻辑编排、事务管理、权限检查
- **Core Layer**: 领域逻辑实现、RAG引擎、文档处理
- **Infrastructure Layer**: 数据持久化、缓存、消息队列

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 + PostgreSQL
- **缓存**: Redis
- **向量数据库**: Qdrant
- **任务队列**: Celery
- **LLM**: Ollama (本地部署)
- **监控**: Prometheus + Grafana
- **日志**: ELK Stack

## 核心特性

- 🏢 多租户支持 + 配额管理
- 📚 6 层知识体系 (topic/concept/summary/recipe/reference/errata)
- 🔍 RAG 检索增强生成 + AI 学习诊断引擎
- 📝 文档勘误管理系统
- 🔗 第三方集成 (飞书/企业微信 Webhook)
- 🔐 CSRF 双 Cookie + JWT 认证
- 🚀 异步任务队列 (Celery + Redis)
- 📊 结构化日志 + 健康检查
- 📈 Prometheus 指标 + Grafana 监控

## 快速开始

```bash
# 启动开发环境
docker compose up -d

# 运行数据库迁移
alembic upgrade head

# 访问 API 文档
open http://localhost:8000/docs
```

### 知识导入

```bash
# Wiki 结构化知识导入（含 frontmatter 元数据）
python3.12 scripts/import_wiki_to_ganfy.py --dry-run
python3.12 scripts/import_wiki_to_ganfy.py --all

# 通用目录导入（任意 .md 目录）
python3.12 scripts/import_directory_to_ganfy.py \
  --source documents/kb --dataset "团队知识库" --dry-run
```

### 部署到预生产

```bash
make build-image
scp image.tar.gz ${REMOTE_HOST}:/tmp/
ssh ${REMOTE_HOST} "docker load < /tmp/image.tar.gz && docker compose up -d"
```

## 目录规范

```
enterprise-rag-v2/
├── api/                    # API 路由、中间件、依赖注入
├── services/               # 业务服务层 (impl + interfaces)
├── core/                   # 领域逻辑 (RAG引擎、文档处理)
├── infrastructure/         # 数据持久化、缓存、消息队列、日志
├── apps/                   # 商业模块 (商业化、集成)
├── alembic/                # 数据库迁移脚本 (24+)
├── frontend/               # Vue 前端 (Vite)
├── requirements/           # runtime.txt + dev.txt
├── scripts/                # 运维脚本、导入工具、部署
│   ├── import_wiki_to_ganfy.py       # Wiki 结构化导入
│   ├── import_directory_to_ganfy.py  # 通用目录导入
│   ├── kb/                           # 知识库健康检查
│   └── deploy/                       # 部署与发布脚本
├── tests/                  # 单元测试 (368+ passing)
├── documents/              # 设计文档
├── docker-compose.yml      # 开发环境
├── docker-compose.deploy.yml # 生产/预生产部署
└── Makefile                # 构建与发布命令
```

## Docker 构建与版本发布

```bash
# 1) 构建版本镜像（会读取 pyproject.toml 的版本）
make build-image

# 2) 发布（镜像 + git tag 一致）
make release VERSION=v2.0.1 REGISTRY=registry.example.com/your-team PUSH=true
```

详细流程见 `RELEASE_PROCESS.md`。

**发布到单机环境（测试/预生产/生产共用）**：在仓库根目录执行 `./scripts/deploy/release-to-102.sh`（默认 `${REMOTE_HOST}`）。该脚本在本机 `docker build` 后通过管道将镜像加载到远端，并下发 `docker-compose.deploy.yml` 与启动脚本。
