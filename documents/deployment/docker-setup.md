# Docker部署

## 环境要求

- Docker 20.10+ 
- Docker Compose 1.29+
- 至少 4GB 内存
- 至少 20GB 磁盘空间

## 目录结构

```
project/
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── backend/
└── frontend/
```

## 配置文件

### docker-compose.yml

```yaml
version: '3.8'

networks:
  rag-network:
    driver: bridge

services:
  backend:
    build:
      context: ../backend
      dockerfile: ../docker/Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      # 生产环境必须通过 secrets 或 CI/CD 注入真实值
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - QDRANT_URL=http://qdrant:6333
      - JWT_SECRET=${JWT_SECRET}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
    depends_on:
      - db
      - redis
      - qdrant
    networks:
      - rag-network

  frontend:
    build:
      context: ../frontend
      dockerfile: ../docker/Dockerfile.frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000/api
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - rag-network

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - rag-network

  redis:
    image: redis:7
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - rag-network

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    networks:
      - rag-network

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

### Dockerfile.backend

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile.frontend

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json .
RUN npm install

COPY . .

RUN npm run build

CMD ["npm", "run", "preview"]
```

## 启动步骤

### 1. 构建镜像

```bash
cd docker
docker-compose build
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 初始化数据库

```bash
docker-compose exec backend python init_db.py
```

### 4. 验证服务

- 后端服务: http://localhost:8000
- 前端服务: http://localhost:3000
- Qdrant: http://localhost:6333

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | 数据库连接字符串 | postgresql://user:password@db:5432/rag_db |
| REDIS_URL | Redis连接字符串 | redis://redis:6379 |
| QDRANT_URL | Qdrant连接字符串 | http://qdrant:6333 |
| JWT_SECRET | JWT密钥 | your_jwt_secret |
| VITE_API_URL | 前端API地址 | http://localhost:8000/api |

> 建议新增 `.env`（仅本机/服务器保存，不提交仓库）:
>
> ```env
> DATABASE_URL=postgresql://user:strong_password@db:5432/rag_db
> POSTGRES_USER=user
> POSTGRES_PASSWORD=strong_password
> POSTGRES_DB=rag_db
> REDIS_PASSWORD=another_strong_password
> JWT_SECRET=replace_with_32_bytes_or_more_secret
> ```

### 持久化存储

- PostgreSQL数据: `postgres_data` 卷
- Redis数据: `redis_data` 卷
- Qdrant数据: `qdrant_data` 卷

## 故障排查

### 服务启动失败

1. 检查Docker服务是否运行
2. 检查端口是否被占用
3. 查看日志:

```bash
docker-compose logs backend
docker-compose logs frontend
docker-compose logs db
```

### 数据库连接失败

1. 检查数据库服务是否正常运行
2. 验证数据库连接字符串
3. 检查数据库用户权限

### Qdrant连接失败

1. 检查Qdrant服务是否正常运行
2. 验证Qdrant连接字符串
3. 检查网络配置

### 前端无法访问后端

1. 检查后端服务是否正常运行
2. 验证前端API地址配置
3. 检查网络配置

## 常用命令

### 查看服务状态

```bash
docker-compose ps
```

### 查看日志

```bash
docker-compose logs -f
```

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart
```

### 进入容器

```bash
docker-compose exec backend bash
docker-compose exec frontend bash
docker-compose exec db psql -U user -d rag_db
```