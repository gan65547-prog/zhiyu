# AI 工作台文档中心

> **治理基线**：2026-08-05
> **产品实施基线**：[AI 工作台产品详细落地方案](design/AI工作台产品详细落地方案-v1.md)（v1.1）
> **代码事实源**：`enterprise-rag-v2/`、`ops-center/` 的实现、迁移与自动化测试优先于说明性文档。

本目录服务于“从企业知识库 RAG 演进为 AI 工作台”的交付。活跃文档只回答三类问题：做什么、当前系统如何运行、怎样安全发布。历史方案、阶段报告、商业化草案和内部复盘不随公开源码发布；当前公开文档见本索引，历史资料处理原则见 [archive/](archive/README.md)。代码许可状态和需留在仓库外的数据边界见[开源边界说明](../OPEN_SOURCE_BOUNDARY.md)。

## 统一口径

| 术语 | 统一定义 | 当前状态 |
|---|---|---|
| AI 工作台 | 面向租户的素材、知识、研究、Agent 与内容协同产品 | 产品目标；以主方案的 P0/P1/P2 分期实施 |
| 企业知识库 RAG | 工作台的现有底座，负责文档处理、检索、引用和问答 | 已有实现，仍是 P0 的基础能力 |
| 行业知识咨询与自动调研 | 工作台“研究中心”的能力，不是第二套产品或独立知识库 | 设计已并入主方案；按研究项目/运行/来源模型实施 |
| Wiki / 长期记忆 | 知识中心的增强能力，必须服务于素材—知识—研究闭环 | P1+，未作为当前上线前置条件 |
| ops-center | 业务侧的独立运维控制面，只经受保护的内部接口访问 | 已有 MVP；运行说明以 `ops-center/README.md` 为准 |

## 活跃文档

### 产品与技术基线

| 文档 | 用途 | 权威性 |
|---|---|---|
| [AI 工作台产品详细落地方案](design/AI工作台产品详细落地方案-v1.md) | 数据模型、接口边界、技术分期和验收实现 | **技术实施基线** |
| [系统实施基线](architecture/system-baseline.md) | 已实现边界、服务拓扑、事实源与变更规则 | **当前技术口径** |
| [架构总览](architecture/overview.md) | 现有 RAG 服务的分层与路由入口 | 辅助参考；与代码一起使用 |
| [数据库设计](architecture/database-design.md) | 当前核心数据实体参考 | 辅助参考；以 ORM 与 Alembic 为准 |
| [安全架构](architecture/security.md) | 认证、授权、隔离和审计原则 | 安全基线；以配置与测试为准 |

### API 与开发

| 文档 | 用途 |
|---|---|
| [API 总览](api/overview.md) | 外部 API 使用约定；具体接口以路由、Schema 和 OpenAPI 为准 |
| [数据模型](api/schemas.md) | 请求/响应模型参考 |
| [快速开始](development/getting-started.md) | 本地开发与启动 |
| [模块职责](development/module-responsibilities.md) | 服务边界 |
| [调用链路](development/call-chain.md) | 核心链路定位 |
| [编码规范](development/coding-standards.md) / [测试指南](development/testing-guide.md) / [贡献指南](development/contributing.md) | 研发质量要求 |
| [工程质量与发布治理](development/工程质量与发布治理.md) | 变更分级、质量门禁、候选证据与封板规则 |
| [文档处理排障](faq/文档分段向量化问题排查FAQ.md) | 当前文档处理问题与排障 |

### 学习资料

| 文档 | 用途 |
|---|---|
| [LLMProvider 设计模式详解](learning/LLMProvider设计模式详解.md) | LLM Provider 抽象与扩展方式 |
| [RAG 核心流程](learning/RAG核心流程.md) | RAG 处理和检索链路说明 |
| [多租户系统架构详解](learning/多租户系统架构详解.md) / [多租户系统使用说明](learning/多租户系统使用说明.md) | 多租户架构和使用说明 |
| [对话流程详解](learning/对话流程详解.md) | 对话请求处理流程 |
| [数据库迁移核心业务流程详解](learning/数据库迁移核心业务流程详解.md) | 数据库迁移业务流程 |
| [租户系统代码审核报告](learning/租户系统代码审核报告.md) | 租户系统代码审查记录 |

### 部署与运行

| 文档 | 用途 |
|---|---|
| [Docker 部署](deployment/docker-setup.md) | 开发/测试环境部署 |
| [生产环境部署](deployment/production-guide.md) | 生产配置与安全要求 |
| [Qdrant 配置](deployment/qdrant-setup.md) | 向量库运行 |
| [监控配置](deployment/monitoring.md) / [备份恢复](deployment/backup-recovery.md) | 可观测与灾备 |
| [发布 Runbook 与验收清单](deployment/release-runbook.md) | 每次发布唯一执行清单与 Go/No-Go 判定 |
| [知识库 Git 同步](deployment/knowledge-sync.md) / [同步发布检查表](deployment/knowledge-sync-release-checklist.md) | 已落地的文档同步流水线 |
| [知识库同步入口](kb/README.md) | 可被同步到 RAG 的仓库知识文档放置规范 |

## 推荐使用路径

1. **产品/研发排期**：先读公开的 AI 工作台技术实施基线和系统实施基线；不要从历史材料反推当前需求。
2. **功能开发**：先看模块职责、调用链路和实际代码；新增工作台模块必须回写主方案的模型、接口、验收项。
3. **发布生产**：只使用生产环境部署、备份恢复和发布 Runbook；任何日期化的上线计划均为历史记录。
4. **运维中心**：使用 `ops-center/README.md` 与 `ops-center/STAGING_CHECKLIST.md`；内部环境清单、发布记录和运营计划不包含在公开文档中。

## 文档变更规则

- 一个能力只保留一个**活跃**方案；设计评审、问题清单和已完成计划必须归档，不能并列为实施依据。
- 代码、数据库迁移、环境变量或 API 契约变化时，同一提交更新对应活跃文档与本索引。
- 涉及数据模型、API 或验收时更新技术实施基线；涉及产品优先级的内部决策不写入公开发布说明；仅在需要可执行操作细节时新增独立 Runbook/指南，并在本页登记入口。
- 活跃文档不得声称“已上线/已完成”，除非有可复现的测试或运行证据；不确定时标为“计划中”。
- `archive/` 仅说明哪些历史资料不进入公开源码；内部原件由维护者在仓库外受控保存。

## 已完成的本轮治理

- 合并产品、行业咨询和自动调研路线为一份主方案。
- 移除失效导航、重复的发布计划、内部阶段报告和并行设计的活跃身份。
- 保留已实现的知识库同步操作入口，并将其归入部署文档。
- 将旧上线计划、发布原始证据和内部历史档案移出公开源码，保留当前文档入口与验收规范。
