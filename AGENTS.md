# 知域工程与发布规则

本仓库以可验证交付为准：代码、测试、候选证据和发布状态必须相互对应，不能以历史报告、HTTP 200、服务启动或 AI 文字说明替代验证。

## 开发规则

1. 新模块、权限/租户隔离、数据迁移、异步任务、外部抓取、CI 或部署改动，先在任务/PR 中写明范围、非目标、风险、验收与回滚。
2. 变更必须保持 `enterprise-rag-v2`（租户业务）与 `ops-center`（内部运维面）的权限边界；资源 ID 必须服务端鉴权，外部 URL 必须经过 SSRF 与限速治理。
3. 每次代码改动至少运行受影响的测试；跨服务、认证、隔离、数据处理或发布改动必须运行对应集成/E2E 回归。
4. 文档的唯一入口是 `documents/README.md`；产品和未来技术方案的唯一基线是 `documents/design/AI工作台产品详细落地方案-v1.md`。
5. 新增或重构代码必须接受结构预算检查：文件 800 行、函数 120 行、复杂度 15 是关注值，不要求机械拆分；历史债务按 baseline 允许有限正常增长并产生 warning，超过增长预算或硬顶才阻断。不得通过刷新 baseline 消除风险。
6. 业务流程必须保持“API 适配 → Service 编排 → Core 领域逻辑 → Infrastructure 适配”的单向边界。API 不得直接写数据库，Core 不得依赖 API，跨模块流程通过接口/事件连接，不得复制第二套任务状态机。
7. 一个 Service 方法只编排一个业务用例；事务边界、权限校验、幂等键、失败状态和重试策略必须在任务或 PR 中明确。复杂流程必须拆成可替换端口并提供失败路径测试。

## 质量门禁

提交前运行：

```bash
bash scripts/quality/run-quality-gates.sh --full
```

该命令校验工作区格式、发布 Profile、活跃文档链接、Python 语法与双服务测试。CI 同样执行，不能用仅本地的成功结果替代 CI 结论。
其中 `check-code-structure.py` 会阻止后端新增或增长的大文件、大函数和高复杂度函数，`check-frontend-structure.py` 对 Vue/TypeScript 执行同样的文件与函数门禁；基线文件只记录既有债务，不是永久豁免。

## 发布封板规则

发布前必须读取 `release/release-profile.json`、`release/README.md` 和 `documents/deployment/release-runbook.md`，并使用当前候选 HEAD 生成证据：

```bash
python3 scripts/quality/collect-release-evidence.py \
  --profile release/release-profile.json \
  --manual-evidence MVP-04=/secure/evidence/backup-restore-and-rollback.md \
  --output /secure/evidence/ganfy-2.1.1.json
python3 scripts/quality/release-preflight.py \
  --profile release/release-profile.json \
  --evidence /secure/evidence/ganfy-2.1.1.json
```

只有证据绑定当前 HEAD、所有 required capability 为 PASS、Profile 状态为 `verified` 或 `approved` 且回滚记录齐全时，才允许创建发布 tag。任何 FAIL、BLOCKED、NOT RUN、UNKNOWN 或证据缺失均为硬阻断。禁止移动或复用 release tag。
