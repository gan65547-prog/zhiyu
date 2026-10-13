# ops-center (MVP)

独立部署的运维中心最小可运行骨架（P0a 起步版）。

## 已实现

- 静态控制台页 `static/index.html`：概览（含业务上游探测）、租户与用量、运维操作与任务、审计、运维用户、**运维命令**（资源上限 / 重建索引 / 缓存失效）。
- 独立 FastAPI 服务
- 健康检查：
  - `GET /health/live`
  - `GET /health/ready`（会检查 upstream，可作为容器 readiness）
  - `GET /api/v1/operations/health/upstream`（探测业务侧 internal admin 可达性）
- 通过 `business_gateway` 透传业务侧内部接口（`/internal/admin/*`）：
  - `GET /api/v1/operations/tenants`
  - `GET /api/v1/operations/tenants/{tenant_id}`
  - `GET /api/v1/operations/tenants/{tenant_id}/usage`
  - `GET /api/v1/operations`
  - `GET /api/v1/operations/audit/logs`
  - `POST /api/v1/operations/tenants/{tenant_id}/quota`
  - `POST /api/v1/operations/documents/reindex`

## 快速启动（本地）

1. 创建并填写环境变量

```bash
cp .env.example .env
```

启动前必须将 `AUTH_SECRET_KEY` 和 `BOOTSTRAP_ADMIN_PASSWORD` 替换成独立随机值；密钥至少 32 个字符，管理员密码至少 12 个字符。示例值不能直接用于运行环境。

2. 安装依赖并运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8081 --reload
```

3. 打开文档与控制台

- [http://localhost:8081/docs](http://localhost:8081/docs)
- **Vue 独立控制台**（需先构建）：`make console-build`，然后访问 [http://localhost:8081/console/](http://localhost:8081/console/) ；开发联调：`make console-dev`（Vite 代理 `/api` → 8081）。

RBAC 说明：读接口（租户列表、审计、上游探测等）面向 `super_admin` / `tenant_ops` / `read_only_auditor`；**租户域写操作**（配额、重建索引、缓存失效）仅 `super_admin` / `tenant_ops`。自动化验证见 `tests/test_rbac_enforcement.py`。

## 对接要求

- 业务服务应可访问，且已启用 `/internal/admin/*`
- `.env` 中需设置：
  - `BUSINESS_BASE_URL`
  - `INTERNAL_API_KEY`
  - `SOURCE_ENV`
  - `AUTH_SECRET_KEY`
  - `BOOTSTRAP_ADMIN_PASSWORD`

## 写操作请求头

写操作必须携带：

- `X-Op-Id`
- `X-Operator`

`X-Op-Id` 需满足基础格式约束（长度与字符集），不合法会返回 `INVALID_X_OP_ID`。

## 网关重试策略

- 仅对读请求（`GET`）启用重试
- 配置项：
  - `GATEWAY_READ_RETRY_COUNT`（默认 1，表示总共 2 次尝试）
  - `GATEWAY_READ_RETRY_BACKOFF_SECONDS`（默认 0.2 秒）
- 网关日志：
  - 成功日志：`gateway_request`
  - 失败日志：`gateway_request_failed`
  - 字段包含 `request_id / op_id / method / path / status_code / attempt / latency_ms`

## 最小测试与联调

```bash
# 路由级单测
pip install -r requirements-dev.txt
pytest -q

# 对已启动服务执行 smoke（真实调用业务侧）
./scripts/smoke.sh

# 仅做参数与环境检查，不触发写调用
BASE_URL=http://127.0.0.1:8081 OP_ID=ops-smoke-001 OPERATOR=ops-smoke ./scripts/smoke.sh --dry-run
```

## 常用命令（Makefile）

```bash
make dev
make test
make smoke
make smoke-dry
make staging-validate
make lint
```

`make staging-validate` 会生成一份 Markdown 联调报告到 `reports/` 目录。

## 部署与上线

- 容器已内置 `HEALTHCHECK`（探测 `/health/ready`）
- Compose 也配置了同等 `healthcheck`
- Staging 发布请按 `STAGING_CHECKLIST.md` 执行


cd /Volumes/TOSHIBA/AIAgent/ganfy/ops-center && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8081 --reload
