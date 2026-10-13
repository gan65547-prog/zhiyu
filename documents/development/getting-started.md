# 快速开始

> 基于实际项目结构生成
> 最后更新: 2026-04-05

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建和开发 |
| PostgreSQL | 15+ | 生产数据库 (开发可用 SQLite) |
| Redis | 7+ | 缓存 + Celery Broker |
| Qdrant | 1.5+ | 向量数据库 |
| Docker & Compose | 最新版 | 容器化部署 (可选) |

## 项目结构

```
enterprise-rag-v2/                 # 项目根目录
├── api/                           # API 层
│   ├── routers/                   # 路由定义
│   │   ├── auth.py                # 认证路由
│   │   ├── tenants.py             # 租户路由
│   │   ├── workspaces.py          # 工作空间路由
│   │   ├── datasets.py            # 数据集路由
│   │   ├── documents.py           # 文档路由
│   │   ├── chat.py                # 对话路由
│   │   ├── oauth.py               # OAuth路由
│   │   ├── backups.py             # 备份恢复路由
│   │   ├── webhooks.py            # Webhook路由
│   │   └── users.py               # 用户管理路由
│   ├── middleware/                # 中间件
│   └── schemas/                   # Pydantic 数据模型
├── services/                      # 服务层
│   ├── interfaces/                # 服务接口定义
│   └── impl/                      # 服务实现
├── core/                          # 核心层
│   ├── config.py                  # Pydantic Settings 配置
│   ├── interfaces/                # 核心接口定义
│   └── security/                  # 安全工具 (JWT, 密码哈希)
├── infrastructure/                # 基础设施层
│   ├── database/
│   │   ├── models.py              # SQLAlchemy ORM 模型 (15张表)
│   │   ├── session.py             # 异步会话工厂
│   │   └── migrations/            # Alembic 迁移脚本
│   ├── cache/                     # Redis 缓存封装
│   ├── storage/                   # 文件存储 (本地/S3)
│   └── monitoring/                # 监控 (健康检查, 指标)
├── frontend/                      # 前端目录
│   ├── src/
│   │   ├── api/                   # API 调用封装
│   │   ├── components/            # Vue 组件
│   │   ├── composables/           # 组合式函数
│   │   ├── layouts/               # 布局组件
│   │   ├── router/                # 路由配置
│   │   ├── stores/                # Pinia 状态管理
│   │   ├── views/                 # 页面组件
│   │   ├── App.vue                # 根组件
│   │   └── main.ts                # 入口文件
│   ├── package.json
│   ├── vite.config.ts             # Vite 配置 (含代理)
│   └── tsconfig.json
├── main.py                        # FastAPI 应用入口
├── requirements.txt               # Python 依赖
├── docker-compose.yml             # Docker Compose 编排
├── .env.example                   # 环境变量示例
└── alembic.ini                    # Alembic 迁移配置
```

## 快速开始 (Docker Compose 一键启动)

```bash
# 1. 克隆项目
git clone <repository-url>
cd enterprise-rag-v2

# 2. 复制环境变量
cp .env.example .env
# 编辑 .env 文件，填写必要的配置（见下方说明）

# 3. 一键启动所有服务
docker-compose up -d --build

# 4. 等待服务就绪后访问
# 后端 API: http://localhost:8000
# 前端界面: http://localhost:3000
# Qdrant: http://localhost:6333/dashboard
# API文档: http://localhost:8000/docs
```

## 手动安装 (开发模式)

### 1. 后端环境搭建

```bash
cd enterprise-rag-v2

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或: venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制并编辑环境变量
cp .env.example .env
# 必须配置: DATABASE_URL, JWT_SECRET_KEY, REDIS_URL 等

# 初始化数据库 (首次运行)
alembic upgrade head

# 启动后端开发服务器 (热重载)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 前端环境搭建

```bash
cd enterprise-rag-v2/frontend

# 安装依赖
npm install

# 启动前端开发服务器 (默认端口 3000)
npm run dev

# Vite 已配置代理:
# /api → http://localhost:8000 (后端API)
# 开发环境下无需额外配置 CORS
```

### 3. 依赖服务启动

#### PostgreSQL (生产模式)

```bash
# 使用 Docker 启动 PostgreSQL
docker run -d \
  --name postgres \
  -e POSTGRES_USER=rag_user \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=rag_db \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15

# 对应 .env 配置:
# DATABASE_URL=postgresql://rag_user:your_password@localhost:5432/rag_db
```

#### Redis

```bash
# 使用 Docker 启动 Redis
docker run -d \
  --name redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine

# 对应 .env 配置:
# REDIS_URL=redis://localhost:6379/0
```

#### Qdrant (向量数据库)

```bash
# 使用 Docker 启动 Qdrant
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest

# 验证 Qdrant 是否正常运行
curl http://localhost:6333/health
# 预期返回: {"status":"ok","version":"..."}
```

## 环境变量配置 (.env)

```bash
# === 数据库配置 ===
DATABASE_URL=postgresql://rag_user:password@localhost:5432/rag_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# === Redis 配置 ===
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=20

# === JWT 认证配置 ===
JWT_SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24小时
REFRESH_TOKEN_EXPIRE_DAYS=30

# === Qdrant 向量数据库 ===
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=documents
QDRANT_VECTOR_SIZE=768  # 根据 embedding_model 调整

# === LLM 配置 ===
LLM_PROVIDER=openai        # openai / deepseek / zhipu
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# === 嵌入模型配置 ===
DEFAULT_EMBEDDING_MODEL=bge-small-zh-v1.5
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# === 应用配置 ===
APP_ENV=development         # development / production
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
LOG_LEVEL=INFO
```

## 数据库迁移

本项目使用 **Alembic** 进行数据库版本管理:

```bash
# 生成新的迁移脚本 (基于 models.py 变更自动生成)
alembic revision --autogenerate -m "描述变更内容"

# 执行迁移到最新版本
alembic upgrade head

# 回滚到上一版本
alembic downgrade -1

# 查看当前数据库版本
alembic current

# 查看迁移历史
alembic history
```

## 验证安装

### 后端验证

```bash
# 访问健康检查端点
curl http://localhost:8000/health
# 预期返回: {"status": "healthy", ...}

# 访问 API 文档 (Swagger UI)
open http://localhost:8000/docs

# 访问指标端点
curl http://localhost:8000/metrics
```

### 前端验证

```bash
# 浏览器打开
open http://localhost:3000

# 应该看到登录页面
# 默认管理员账号需要在数据库中初始化创建
```

## 常见问题排查

### 1. 后端启动失败: "Database connection error"

**原因**: PostgreSQL 未启动或连接字符串错误

**解决**:
```bash
# 检查 PostgreSQL 是否运行
docker ps | grep postgres
# 或: systemctl status postgresql

# 检查 .env 中的 DATABASE_URL 是否正确
# 格式: postgresql://user:pass@host:port/dbname
```

### 2. 前端请求返回 404

**原因**: Vite 代理未正确转发到后端

**解决**:
```bash
# 确保 vite.config.ts 中代理配置正确:
# proxy: {
#   '/api': { target: 'http://localhost:8000', changeOrigin: true }
# }

# 确保后端在 8000 端口运行
curl http://localhost:8000/health
```

### 3. Qdrant 连接失败

**原因**: Qdrant 未启动或端口被占用

**解决**:
```bash
# 检查 Qdrant 是否运行
docker ps | grep qdrant

# 手动重启
docker restart qdrant

# 查看日志
docker logs qdrant
```

### 4. 登录后页面空白 / 权限问题

**原因**: Token 未正确传递或认证状态未初始化

**解决**:
```bash
# 检查浏览器控制台是否有报错
# 确认 localStorage 中有 token 存储
# 确认 MainLayout.vue 中调用了 authStore.initialize()
```

### 5. Celery Worker 任务不执行

**原因**: Celery Worker 未启动或 Redis 连接失败

**解决**:
```bash
# 启动 Celery Worker
celery -A tasks worker --loglevel=info -B

# 检查 Redis 连接
redis-cli ping
# 应返回 PONG
```

## 开发工作流

```bash
# 1. 创建功能分支
git checkout -b feature/your-feature-name

# 2. 开发完成后运行测试
pytest tests/ -v

# 3. 代码格式化 (后端)
black .
isort .

# 4. 代码格式化 (前端)
npm run lint
npm run format

# 5. 提交代码
git add .
git commit -m "feat: description of your feature"

# 6. 推送到远程
git push origin feature/your-feature-name
```
