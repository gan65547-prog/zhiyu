# API 路由说明（已实现）

本文档描述当前代码中已落地的路由模块，不再使用“待创建”表述。

## 核心路由（`api/routers/`）

| 文件 | 前缀 | 主要能力 |
|------|------|----------|
| `auth.py` | `/api/v1/auth` | 注册、登录、令牌刷新、当前用户 |
| `tenants.py` | `/api/v1/tenants` | 租户管理 |
| `workspaces.py` | `/api/v1/workspaces` | 工作空间与成员管理 |
| `datasets.py` | `/api/v1/datasets` | 数据集管理 |
| `documents.py` | `/api/v1/documents` | 文档上传、列表、删除、重建索引 |
| `chat.py` | `/api/v1/chat` | 会话、消息、流式对话 |
| `oauth.py` | `/api/v1/oauth` | 第三方登录 |
| `backups.py` | `/api/v1/backups` | 备份与恢复 |
| `webhooks.py` | `/api/v1/webhooks` | 回调入口 |
| `users.py` | `/api/v1/users` | 用户与权限相关操作 |

## 自托管资源路由（`apps/commercialization/routers/`）

| 文件 | 前缀 | 主要能力 |
|------|------|----------|
| `quotas.py` | `/api/v1/quotas` | 资源用量统计与管理员配置上限查询 |

## 集成路由（`apps/integration/routers/`）

| 文件 | 前缀 | 主要能力 |
|------|------|----------|
| `chat.py` | `/api/v1/integration/chat` | 飞书/企微消息接入与路由 |
| `bind.py` | `/api/v1/integration/bind` | 外部账号绑定 |
| `health.py` | `/api/v1/integration/health` | 集成模块健康检查 |
| `platform_app_admin.py` | `/api/v1/integration/admin/platform-apps` | 平台应用配置管理 |

## 路由注册位置

统一在 `main.py` 中通过 `app.include_router(...)` 注册。当前开源版不包含支付、订阅销售或兑换码 API。
