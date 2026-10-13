# 版本发布与部署流程

本文档描述企业级 RAG 系统从开发到上线的完整流程。

---

## 一、环境说明

| 环境 | 用途 | 依赖 |
|------|------|------|
| 开发环境 | 本地调试 | `requirements/dev.txt` |
| 测试环境 | CI/CD 自动测试 | Docker 容器 |
| 生产环境 | 实际运行 | `requirements/runtime.txt` |

---

## 二、版本号规范

采用语义化版本 `v主版本.次版本.修订号`：

- **主版本 (MAJOR)**：不兼容的 API 变更
- **次版本 (MINOR)**：向后兼容的功能新增
- **修订号 (PATCH)**：向后兼容的问题修复

示例：`v2.1.0`

---

## 三、开发流程

### 1. 功能开发

```bash
# 创建功能分支
git checkout -b feature/xxx

# 开发完成后提交
git add .
git commit -m "feat: add xxx"
```

### 2. 代码审查

- 提交 Pull Request
- 通过 CI 测试
- 至少 1 人 Code Review

### 3. 合并到主分支

```bash
git checkout main
git merge feature/xxx
git push origin main
```

---

## 四、版本发布

### 1. 发布前检查

- [ ] 主分支代码已合并
- [ ] 所有 CI 测试通过
- [ ] `git status` 工作区干净
- [ ] 确定版本号（如 `v2.1.0`）
- [ ] 更新 `pyproject.toml` 中的版本号（可选）

### 2. 执行发布

```bash
# 方式一：使用 Make（推荐）
make release VERSION=v2.1.0 PUSH=true

# 方式二：直接调用脚本
bash scripts/release/release.sh --version v2.1.0 --push
```

### 3. 发布脚本执行内容

| 步骤 | 说明 |
|------|------|
| 1 | 检查 git 工作区是否干净 |
| 2 | 构建 Docker 镜像 |
| 3 | 打版本标签 `v2.1.0` 和 `latest` |
| 4 | 创建 git annotated tag |
| 5 | 推送镜像到 registry（可选） |
| 6 | 推送 git tag 到远程 |

### 4. 手动构建（不推荐）

```bash
# 如果需要手动构建
docker build \
  --label org.opencontainers.image.version="v2.1.0" \
  -t enterprise-rag-v2:v2.1.0 \
  -t enterprise-rag-v2:latest \
  .
```

---

## 五、部署流程

### 1. 环境准备

```bash
# SSH 到目标服务器
ssh user@production-server

# 拉取最新镜像
docker pull registry.example.com/your-team/enterprise-rag-v2:v2.1.0
```

### 2. 更新配置

确保环境变量正确配置：

```bash
# 数据库配置
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/rag
REDIS_URL=redis://host:6379/0

# Qdrant 配置
QDRANT_URL=http://qdrant:6333

# LLM 配置
LLM_PROVIDER=openai  # 或 ollama / vllm
OPENAI_API_KEY=sk-xxx

# 日志级别
LOG_LEVEL=INFO
```

### 3. 启动服务

```bash
# 使用 docker-compose 启动
docker-compose up -d

# 或直接启动容器
docker run -d \
  --name enterprise-rag \
  -p 8000:8000 \
  -e DATABASE_URL="..." \
  -e REDIS_URL="..." \
  -e QDRANT_URL="..." \
  -e LLM_PROVIDER="openai" \
  -e OPENAI_API_KEY="sk-xxx" \
  enterprise-rag-v2:v2.1.0
```

### 4. 健康检查

```bash
# 检查容器状态
docker ps | grep enterprise-rag

# 检查 API 健康状态
curl http://localhost:8000/api/v1/health

# 查看日志
docker logs enterprise-rag --tail 100
```

---

## 六、回滚流程

### 1. 查看可用版本

```bash
# 列出本地镜像
docker images | grep enterprise-rag

# 列出 git tags
git tag -l
```

### 2. 执行回滚

```bash
# 停止当前容器
docker-compose down

# 使用旧版本镜像启动
docker run -d \
  --name enterprise-rag \
  -p 8000:8000 \
  enterprise-rag-v2:v2.0.0
```

### 3. 代码回滚

```bash
# 回滚到指定版本
git checkout v2.0.0

# 或回滚到上一个版本
git checkout HEAD~1
```

---

## 七、溯源方法

给定线上镜像版本（如 `v2.1.0`）：

```bash
# 1. 定位源码
git checkout v2.1.0

# 2. 查看对应提交
git show v2.1.1

# 3. 查看镜像元信息
docker inspect enterprise-rag-v2:v2.1.0
```

---

## 八、禁止事项

- ❌ 禁止无 tag 直接上线
- ❌ 禁止手工修改镜像后再上线
- ❌ 禁止把 `.env` 文件打入镜像
- ❌ 禁止在生产环境直接修改代码
- ❌ 禁止把敏感信息硬编码到代码中

---

## 九、常用命令速查

| 操作 | 命令 |
|------|------|
| 开发依赖安装 | `make dev-deps` |
| 构建镜像 | `make build-image` |
| 发布版本 | `make release VERSION=v2.1.0 PUSH=true` |
| 查看日志 | `docker logs -f enterprise-rag` |
| 进入容器 | `docker exec -it enterprise-rag bash` |
| 回滚版本 | `docker pull enterprise-rag-v2:v2.0.0` |


# 十、实际打包命令

```bash
 echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
```
cd enterprise-rag-v2

make build-image VERSION=v2.0.1

 make release VERSION=v2.0.1 REGISTRY=ghcr.io/gan65547-prog PUSH=true
 