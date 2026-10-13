# 数据库设计

> 基于实际代码 `enterprise-rag-v2/infrastructure/database/models.py` 生成
> 最后更新: 2026-04-05

## 数据模型ER图

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    tenants   │     │    users     │     │  workspaces   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id (PK)      │◄────┤ tenant_id(FK)│◄────┤ tenant_id(FK)│
│ name         │     │ current_ws(FK)│     │ name         │
│ contact_email│     │ username     │     │ description  │
│ plan         │     │ email        │     │ is_default   │
│ status       │     │ hashed_pwd   │     └──────┬───────┘
│ extra_meta   │     │ is_superuser  │            │
└──────┬───────┘     │ is_active     │     ┌──────▼───────┐
       │             │ extra_meta   │     │workspace_mem. │
       │             └──────┬───────┘     ├──────────────┤
       │                    │             │ workspace_id(FK)│
       │                    │             │ user_id (FK)   │
       │                    │             │ role          │
       │                    │             └──────┬───────┘
       ▼                    ▼                    │
┌──────────────┐     ┌──────────────┐           │
│  datasets    │     │ conversations│           │
├──────────────┤     ├──────────────┤           │
│ id (PK)      │     │ id (PK)      │           │
│ workspace_id │◄────┤ dataset_id   │           │
│ name         │     │ user_id (FK) │           │
│ embedding_   │     │ title        │           │
│ model        │     │ extra_meta   │           │
│ chunk_size   │     └──────┬───────┘           │
│ chunk_overlap│            │                    │
└──────┬───────┘     ┌──────▼───────┐           │
       │             │   messages   │           │
       │             ├──────────────┤           │
       ▼             │ conversation │           │
┌──────────────┐     │ _id (FK)     │           │
│  documents   │     │ role         │           │
├──────────────┤     │ content      │           │
│ id (PK)      │     │ retrieved_   │           │
│ dataset_id   │     │ chunks       │           │
│ file_name    │     │ tokens_used  │           │
│ file_type    │     └──────────────┘           │
│ file_size    │                                │
│ file_path    │     ┌──────────────┐           │
│ status       │     │document_chunks│           │
│ tags         │     ├──────────────┤           │
│ chunk_count  │     │ document_id  │───────────┘
└──────┬───────┘     │ chunk_index  │
       │             │ content      │
       ▼             └──────────────┘
┌──────────────┐
│ oauth_accounts│
├──────────────┤
│ user_id (FK) │
│ provider     │
│ provider_uid │
│ access_token │
└──────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  audit_logs   │  │   api_keys   │  │ user_configs │  │ user_api_keys │  │login_activities│
├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
│ action       │  │ user_id (FK) │  │ theme        │  │ provider      │  │ ip_address    │
│ resource_type│  │ key_hash     │  │ language     │  │ api_key_enc   │  │ status        │
│ resource_id  │  │ name         │  │ llm_model    │  │ base_url      │  │ error_message │
│ details      │  │ is_active    │  │ temperature  │  │ is_default    │  └──────────────┘
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 枚举类型定义

### TenantStatus (租户状态)
| 值 | 描述 |
|----|------|
| `active` | 活跃 |
| `suspended` | 暂停 |
| `deleted` | 已删除 |

### Tenant plan (历史兼容字段)
| 值 | 描述 |
|----|------|
| `free` | 历史默认值，不控制功能 |
| `basic` | 历史兼容值，不控制功能 |
| `pro` | 历史兼容值，不控制功能 |
| `enterprise` | 历史兼容值，不控制功能 |

### WorkspaceRole (工作空间角色)
| 值 | 描述 |
|----|------|
| `owner` | 所有者 |
| `admin` | 管理员 |
| `member` | 成员 |
| `viewer` | 访客 |

### DocumentStatus (文档状态)
| 值 | 描述 |
|----|------|
| `pending` | 待处理 |
| `processing` | 处理中 |
| `completed` | 已完成 |
| `failed` | 失败 |

### DocumentType (文档类型)
| 值 | 描述 |
|----|------|
| `pdf` | PDF文档 |
| `docx` | Word文档 |
| `txt` | 文本文件 |
| `md` | Markdown |
| `html` | HTML网页 |
| `epub` | 电子书 |

### ThemeMode (主题模式)
| 值 | 描述 |
|----|------|
| `light` | 浅色模式 |
| `dark` | 深色模式 |
| `auto` | 自动跟随系统 |

### Language (语言)
| 值 | 描述 |
|----|------|
| `zh-CN` | 简体中文 |
| `en-US` | 美式英语 |

---

## 表结构详细设计

### 1. tenants (租户表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 租户ID |
| name | String(100) | NOT NULL | 租户名称 |
| contact_email | String(255) | NOT NULL | 联系邮箱 |
| contact_phone | String(50) | | 联系电话 |
| plan | Enum(SubscriptionPlan) | NOT NULL, DEFAULT 'free' | 历史兼容字段；不控制功能或资源上限 |
| status | Enum(TenantStatus) | NOT NULL, DEFAULT 'active' | 租户状态 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_tenant_status, idx_tenant_plan, idx_tenant_email

**关系**: users (一对多), workspaces (一对多)

---

### 2. users (用户表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 用户ID |
| tenant_id | String(36) | FOREIGN KEY → tenants.id, NOT NULL | 所属租户ID |
| current_workspace_id | String(36) | FOREIGN KEY → workspaces.id | 当前工作空间ID |
| username | String(50) | UNIQUE, NOT NULL | 用户名 |
| email | String(255) | UNIQUE, NOT NULL | 邮箱 |
| hashed_password | String(255) | NOT NULL | 密码哈希 |
| is_active | Boolean | NOT NULL, DEFAULT TRUE | 是否激活 |
| is_superuser | Boolean | NOT NULL, DEFAULT FALSE | 是否超级管理员 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_user_tenant, idx_user_email, idx_user_username, idx_user_current_workspace

**关系**: tenant (多对一), workspace_members (一对多), oauth_accounts (一对多)

---

### 3. workspaces (工作空间表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 工作空间ID |
| tenant_id | String(36) | FOREIGN KEY → tenants.id, NOT NULL | 所属租户ID |
| name | String(100) | NOT NULL | 工作空间名称 |
| description | Text | | 工作空间描述 |
| is_default | Boolean | NOT NULL, DEFAULT FALSE | 是否默认工作空间 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_workspace_tenant, idx_workspace_name

**关系**: tenant (多对一), members (一对多), datasets (一对多)

---

### 4. workspace_members (工作空间成员表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 成员关系ID |
| workspace_id | String(36) | FOREIGN KEY → workspaces.id, NOT NULL | 工作空间ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL | 用户ID |
| role | Enum(WorkspaceRole) | NOT NULL, DEFAULT 'member' | 成员角色 |
| joined_at | DateTime | NOT NULL, DEFAULT now() | 加入时间 |

**唯一约束**: uq_workspace_user (workspace_id + user_id)

**索引**: idx_workspace_member_workspace, idx_workspace_member_user

**关系**: workspace (多对一), user (多对一)

---

### 5. datasets (数据集/知识库表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 数据集ID |
| workspace_id | String(36) | FOREIGN KEY → workspaces.id, NOT NULL | 所属工作空间ID |
| name | String(100) | NOT NULL | 数据集名称 |
| description | Text | | 数据集描述 |
| embedding_model | String(255) | NOT NULL | 向量嵌入模型名称 |
| chunk_size | Integer | NOT NULL, DEFAULT 500 | 分块大小 |
| chunk_overlap | Integer | NOT NULL, DEFAULT 50 | 分块重叠大小 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_dataset_workspace, idx_dataset_name

**关系**: workspace (多对一), documents (一对多), conversations (一对多)

---

### 6. documents (文档表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 文档ID |
| dataset_id | String(36) | FOREIGN KEY → datasets.id, NOT NULL | 所属数据集ID |
| file_name | String(255) | NOT NULL | 文件名 |
| file_type | Enum(DocumentType) | NOT NULL | 文件类型 |
| file_size | Integer | NOT NULL | 文件大小(字节) |
| file_path | String(500) | NOT NULL | 存储路径 |
| status | Enum(DocumentStatus) | NOT NULL, DEFAULT 'pending' | 处理状态 |
| tags | JSON | DEFAULT [] | 标签列表 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| chunk_count | Integer | DEFAULT 0 | 分块数量 |
| indexed_at | DateTime | | 索引完成时间 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_document_dataset, idx_document_status, idx_document_type

**关系**: dataset (多对一), chunks (一对多)

---

### 7. document_chunks (文档分块表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 分块ID |
| document_id | String(36) | FOREIGN KEY → documents.id, NOT NULL | 所属文档ID |
| chunk_index | Integer | NOT NULL | 分块序号 |
| content | Text | NOT NULL | 分块内容 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |

**唯一约束**: uq_document_chunk (document_id + chunk_index)

**索引**: idx_chunk_document

**关系**: document (多对一)

---

### 8. conversations (会话/对话表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 会话ID |
| dataset_id | String(36) | FOREIGN KEY → datasets.id, NOT NULL | 所属数据集ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL | 创建者ID |
| title | String(255) | | 会话标题 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_conversation_dataset, idx_conversation_user

**关系**: dataset (多对一), user (多对一), messages (一对多)

---

### 9. messages (消息表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 消息ID |
| conversation_id | String(36) | FOREIGN KEY → conversations.id, NOT NULL | 所属会话ID |
| role | String(20) | NOT NULL | 角色(user/assistant/system) |
| content | Text | NOT NULL | 消息内容 |
| retrieved_chunks | JSON | | RAG检索到的文档片段 |
| tokens_used | Integer | | Token使用量 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |

**索引**: idx_message_conversation, idx_message_role

**关系**: conversation (多对一)

---

### 10. oauth_accounts (OAuth账户表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | OAuth账户ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL | 关联用户ID |
| provider | String(50) | NOT NULL | 第三方提供商(github/google等) |
| provider_user_id | String(255) | NOT NULL | 第三方用户ID |
| access_token | Text | | 访问令牌 |
| refresh_token | Text | | 刷新令牌 |
| expires_at | DateTime | | 过期时间 |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**唯一约束**: uq_oauth_provider_user (provider + provider_user_id)

**索引**: idx_oauth_user, idx_oauth_provider

**关系**: user (多对一)

---

### 11. audit_logs (审计日志表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 日志ID |
| action | String(50) | NOT NULL | 操作类型(create/read/update/delete/login等) |
| resource_type | String(50) | NOT NULL | 资源类型(user/workspace/dataset等) |
| resource_id | String(255) | | 资源ID |
| user_id | String(36) | FOREIGN KEY → users.id | 操作用户ID |
| tenant_id | String(36) | FOREIGN KEY → tenants.id | 租户ID |
| workspace_id | String(36) | FOREIGN KEY → workspaces.id | 工作空间ID |
| ip_address | String(50) | | 客户端IP地址 |
| user_agent | Text | | User-Agent信息 |
| details | JSON | DEFAULT {} | 操作详情 |
| status | String(20) | DEFAULT 'success' | 操作结果(success/failed) |
| error_message | Text | | 错误信息 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |

**索引**: idx_audit_user, idx_audit_tenant, idx_audit_action, idx_audit_resource, idx_audit_created

---

### 12. api_keys (API密钥表 - 系统级)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 密钥ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL | 所有者ID |
| name | String(100) | NOT NULL | 密钥名称 |
| key_hash | String(255) | NOT NULL | 密钥哈希值 |
| last_used_at | DateTime | | 最后使用时间 |
| expires_at | DateTime | | 过期时间 |
| is_active | Boolean | NOT NULL, DEFAULT TRUE | 是否有效 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |

**索引**: idx_api_key_user, idx_api_key_hash

---

### 13. user_configs (用户配置表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 配置ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL, UNIQUE | 用户ID(一对一) |
| **系统设置** | | | |
| theme | Enum(ThemeMode) | NOT NULL, DEFAULT 'light' | 主题模式 |
| language | Enum(Language) | NOT NULL, DEFAULT 'zh-CN' | 界面语言 |
| default_page | String(100) | NOT NULL, DEFAULT '/' | 默认页面 |
| **模型配置** | | | |
| embedding_model | String(255) | NOT NULL, DEFAULT 'bge-small-zh-v1.5' | 默认嵌入模型 |
| llm_model | String(255) | NOT NULL, DEFAULT 'deepseek-chat' | 默认LLM模型 |
| temperature | Float | NOT NULL, DEFAULT 0.7 | 生成温度 |
| top_k | Integer | NOT NULL, DEFAULT 5 | 检索返回数量 |
| **安全设置** | | | |
| session_timeout_minutes | Integer | NOT NULL, DEFAULT 1440 | 会话超时(分钟) |
| two_factor_auth_enabled | Boolean | NOT NULL, DEFAULT FALSE | 双因素认证 |
| ip_whitelist | Text | | IP白名单 |
| **扩展元数据** | | | |
| extra_metadata | JSON | DEFAULT {} | 扩展元数据 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**唯一约束**: uq_user_config_user (user_id)

**索引**: idx_user_config_user

---

### 14. user_api_keys (用户API密钥表 - 第三方服务)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 密钥ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL | 所有者ID |
| provider | String(50) | NOT NULL | 服务提供商(openai/deepseek等) |
| name | String(100) | NOT NULL | 密钥名称 |
| api_key_encrypted | Text | NOT NULL | 加密的API密钥 |
| base_url | String(500) | | 自定义API端点 |
| is_active | Boolean | NOT NULL, DEFAULT TRUE | 是否有效 |
| is_default | Boolean | NOT NULL, DEFAULT FALSE | 是否为默认密钥 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 创建时间 |
| updated_at | DateTime | NOT NULL, DEFAULT now() | 更新时间 |

**索引**: idx_user_api_key_user, idx_user_api_key_provider

---

### 15. login_activities (登录活动表)

| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | String(36) | PRIMARY KEY, UUID | 活动记录ID |
| user_id | String(36) | FOREIGN KEY → users.id, NOT NULL | 用户ID |
| ip_address | String(50) | NOT NULL | 登录IP地址 |
| user_agent | Text | | User-Agent信息 |
| location | String(255) | | 地理位置 |
| status | String(20) | NOT NULL, DEFAULT 'success' | 登录结果(success/failed) |
| error_message | Text | | 失败原因 |
| created_at | DateTime | NOT NULL, DEFAULT now() | 登录时间 |

**索引**: idx_login_activity_user, idx_login_activity_created

---

## 索引汇总

### 主键索引
所有表的 `id` 字段均为 String(36) 类型的主键，使用UUID格式。

### 外键索引
| 外键字段 | 目标表 | 级联策略 |
|---------|--------|---------|
| users.tenant_id | tenants | CASCADE |
| users.current_workspace_id | workspaces | SET NULL |
| workspaces.tenant_id | tenants | CASCADE |
| workspace_members.workspace_id | workspaces | CASCADE |
| workspace_members.user_id | users | CASCADE |
| datasets.workspace_id | workspaces | CASCADE |
| documents.dataset_id | datasets | CASCADE |
| document_chunks.document_id | documents | CASCADE |
| conversations.dataset_id | datasets | CASCADE |
| conversations.user_id | users | CASCADE |
| messages.conversation_id | conversations | CASCADE |
| oauth_accounts.user_id | users | CASCADE |
| audit_logs.user_id | users | SET NULL |
| audit_logs.tenant_id | tenants | SET NULL |
| audit_logs.workspace_id | workspaces | SET NULL |
| api_keys.user_id | users | CASCADE |
| user_configs.user_id | users | CASCADE |
| user_api_keys.user_id | users | CASCADE |
| login_activities.user_id | users | CASCADE |

### 唯一约束
| 约束名 | 表 | 字段 |
|---------|-----|------|
| uq_workspace_user | workspace_members | workspace_id + user_id |
| uq_document_chunk | document_chunks | document_id + chunk_index |
| uq_oauth_provider_user | oauth_accounts | provider + provider_user_id |
| uq_user_config_user | user_configs | user_id |
| users.username | users | username |
| users.email | users | email |

### 性能优化索引
| 索引名 | 表 | 字段 | 用途 |
|---------|-----|------|------|
| idx_tenant_status | tenants | status | 按状态筛选租户 |
| idx_tenant_plan | tenants | plan | 按计划筛选租户 |
| idx_user_email | users | email | 登录查询 |
| idx_user_username | users | username | 登录查询 |
| idx_dataset_workspace | datasets | workspace_id | 查询知识库列表 |
| idx_document_dataset | documents | dataset_id | 查询文档列表 |
| idx_document_status | documents | status | 按状态筛选文档 |
| idx_conversation_user | conversations | user_id | 查询用户会话列表 |
| idx_message_conversation | messages | conversation_id | 查询会话消息 |
| idx_audit_created | audit_logs | created_at | 日志时间范围查询 |

---

## 数据库迁移管理

本项目使用 **Alembic** 进行数据库版本管理和迁移。

### 迁移脚本位置
```
enterprise-rag-v2/
├── alembic.ini
├── alembic/
│   ├── versions/
│   │   ├── 001_initial.py          # 初始建表
│   │   ├── 002_add_indexes.py      # 添加索引
│   │   └── ...                     # 后续迁移
│   └── env.py
```

### 常用命令
```bash
# 生成新的迁移脚本
alembic revision --autogenerate -m "description"

# 执行迁移到最新版本
alembic upgrade head

# 回滚到上一版本
alembic downgrade -1

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

---

## 查询优化建议

1. **使用复合索引**: 对于常用的组合查询条件（如 user_id + visibility），创建复合索引
2. **避免 SELECT ***: 只查询需要的字段，减少数据传输量
3. **合理使用 JOIN**: 使用 EXPLAIN ANALYZE 分析查询计划，确保使用正确的索引
4. **分页优化**: 大数据量场景下使用游标分页替代 OFFSET 分页
5. **读写分离**: 高并发场景下考虑主从复制和读写分离
6. **连接池配置**: 合理设置连接池大小（推荐: min=5, max=20）
