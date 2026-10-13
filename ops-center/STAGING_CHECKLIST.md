# ops-center Staging 上线检查清单

## 1. 环境与配置

- [ ] 已复制 `.env.example` 为 `.env`
- [ ] `BUSINESS_BASE_URL` 指向目标业务环境（如 `https://business-staging.xxx.com`）
- [ ] `INTERNAL_API_KEY` 已配置且与业务侧 `INTERNAL_API_KEYS` 一致
- [ ] `SOURCE_ENV` 设置为 `ops-center-staging`
- [ ] 网络策略已允许 ops-center 访问业务侧 `/internal/admin/*`

## 2. 业务侧前置确认

- [ ] 业务侧已部署包含 `/internal/admin/*` 的版本
- [ ] 业务侧已启用内部鉴权（API Key + IP 白名单）
- [ ] ops-center 出口 IP 已加入业务侧白名单
- [ ] 业务侧健康检查正常（`/health/live`）

## 3. 部署步骤

- [ ] 执行镜像构建：`docker compose build`
- [ ] 启动服务：`docker compose up -d`
- [ ] 确认容器健康：`docker compose ps`（`healthy`）
- [ ] 访问 `http://<host>:8081/health/live` 返回 `alive`
- [ ] 访问 `http://<host>:8081/health/ready` 返回 200
- [ ] 访问 `http://<host>:8081/docs` 确认接口文档可见

## 4. 联调与验收

- [ ] `make smoke-dry` 通过（参数与环境）
- [ ] `make smoke` 通过（真实链路）
- [ ] `make staging-validate` 生成联调报告（`reports/staging-validation-*.md`）
- [ ] 读接口联调：
  - [ ] `/api/v1/operations/tenants`
  - [ ] `/api/v1/operations`
  - [ ] `/api/v1/operations/audit/logs`
- [ ] 写接口联调（携带 `X-Op-Id` / `X-Operator`）：
  - [ ] `quota`
  - [ ] `documents/reindex`

## 5. 观测与日志

- [ ] 可检索到 `gateway_request` 日志
- [ ] 异常时可检索到 `gateway_request_failed` 日志
- [ ] 已验证 `request_id/op_id/path/status_code/latency_ms` 字段存在

## 6. 回滚预案

- [ ] 停用 ops-center：`docker compose down`
- [ ] 业务侧保持原内部接口能力不变（不影响主链路）
- [ ] 如需紧急封禁，业务侧撤销该 `INTERNAL_API_KEY` 或移出白名单
