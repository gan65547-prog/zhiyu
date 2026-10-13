-- ============================================================
-- Enterprise RAG V2 数据库统一 Schema
-- ============================================================
-- 用途：统一预生产和生产环境的数据库结构
-- 来源：基于 ORM models.py 和预生产环境实际 schema
-- ============================================================

-- 1. 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. 枚举类型
CREATE TYPE documentstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
CREATE TYPE documenttype AS ENUM ('PDF', 'DOCX', 'TXT', 'MD', 'HTML', 'EPUB');
CREATE TYPE subscriptionplan AS ENUM ('FREE', 'BASIC', 'PRO', 'ENTERPRISE');
CREATE TYPE tenantstatus AS ENUM ('ACTIVE', 'SUSPENDED', 'DELETED');
CREATE TYPE workspacerole AS ENUM ('OWNER', 'ADMIN', 'MEMBER', 'VIEWER');

-- 3. 函数
CREATE FUNCTION set_updated_at_timestamp() RETURNS trigger AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 表结构
-- ============================================================

-- alembic_version (Alembic 迁移版本记录)
CREATE TABLE alembic_version (
    version_num character varying(128) NOT NULL
);

-- tenants (租户表)
CREATE TABLE tenants (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    name character varying(100) NOT NULL,
    contact_email character varying(255) NOT NULL,
    contact_phone character varying(50),
    plan subscriptionplan DEFAULT 'FREE' NOT NULL,
    status tenantstatus DEFAULT 'ACTIVE' NOT NULL,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- users (用户表)
CREATE TABLE users (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    current_workspace_id uuid,
    username character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_superuser boolean DEFAULT false NOT NULL,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- workspaces (工作空间表)
CREATE TABLE workspaces (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    is_default boolean DEFAULT false NOT NULL,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- workspace_members (工作空间成员表)
CREATE TABLE workspace_members (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    workspace_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role workspacerole DEFAULT 'MEMBER' NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL
);

-- datasets (数据集表)
CREATE TABLE datasets (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    workspace_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    is_public boolean DEFAULT false NOT NULL,
    embedding_model character varying(255) NOT NULL,
    chunk_size integer DEFAULT 500 NOT NULL,
    chunk_overlap integer DEFAULT 50 NOT NULL,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- documents (文档表)
CREATE TABLE documents (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    dataset_id uuid NOT NULL,
    file_name character varying(255) NOT NULL,
    file_type documenttype NOT NULL,
    file_size integer NOT NULL,
    file_path character varying(500) NOT NULL,
    status documentstatus DEFAULT 'PENDING' NOT NULL,
    tags json DEFAULT '[]'::json,
    extra_metadata json DEFAULT '{}'::json,
    chunk_count integer DEFAULT 0,
    indexed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- document_chunks (文档块表)
CREATE TABLE document_chunks (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

-- document_copy_status (文档复制状态追踪表)
CREATE TABLE document_copy_status (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    dataset_id uuid NOT NULL,
    task_id character varying(255),
    total_documents integer DEFAULT 0,
    completed_documents integer DEFAULT 0,
    failed_documents integer DEFAULT 0,
    status character varying(50) DEFAULT 'pending',
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- conversations (会话表)
CREATE TABLE conversations (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    dataset_id uuid NOT NULL,
    user_id uuid NOT NULL,
    workspace_id uuid,
    title character varying(255),
    visibility character varying(20) DEFAULT 'private' NOT NULL,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- messages (消息表)
CREATE TABLE messages (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    conversation_id uuid NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    retrieved_chunks json,
    tokens_used integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

-- oauth_accounts (OAuth账户表)
CREATE TABLE oauth_accounts (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    provider character varying(50) NOT NULL,
    provider_user_id character varying(255) NOT NULL,
    access_token text,
    refresh_token text,
    expires_at timestamp with time zone,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- audit_logs (审计日志表)
CREATE TABLE audit_logs (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    action character varying(50) NOT NULL,
    resource_type character varying(50) NOT NULL,
    resource_id character varying(255),
    user_id uuid,
    tenant_id uuid,
    workspace_id uuid,
    ip_address character varying(50),
    user_agent text,
    details json DEFAULT '{}'::json,
    status character varying(20) DEFAULT 'success',
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

-- api_keys (API密钥表)
CREATE TABLE api_keys (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    key_hash character varying(255) NOT NULL,
    last_used_at timestamp with time zone,
    expires_at timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

-- user_configs (用户配置表)
CREATE TABLE user_configs (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    theme character varying(20) DEFAULT 'light' NOT NULL,
    language character varying(20) DEFAULT 'zh-CN' NOT NULL,
    default_page character varying(100) DEFAULT '/' NOT NULL,
    embedding_model character varying(255) DEFAULT 'bge-small-zh-v1.5' NOT NULL,
    llm_model character varying(255) DEFAULT 'deepseek-chat' NOT NULL,
    temperature numeric(3,2) DEFAULT 0.7 NOT NULL,
    top_k integer DEFAULT 5 NOT NULL,
    session_timeout_minutes integer DEFAULT 1440 NOT NULL,
    two_factor_auth_enabled boolean DEFAULT false NOT NULL,
    ip_whitelist text,
    extra_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- user_api_keys (用户API密钥表)
CREATE TABLE user_api_keys (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    provider character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    api_key_encrypted text NOT NULL,
    base_url character varying(500),
    is_active boolean DEFAULT true NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- login_activities (登录活动表)
CREATE TABLE login_activities (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    ip_address character varying(50) NOT NULL,
    user_agent text,
    location character varying(255),
    status character varying(20) DEFAULT 'success' NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

-- ops_users (运维用户表)
CREATE TABLE ops_users (
    id character varying(36) NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_login_at timestamp without time zone,
    user_ref_id character varying(36),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

-- ops_roles (运维角色表)
CREATE TABLE ops_roles (
    id character varying(36) NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

-- ops_user_roles (运维用户角色关联表)
CREATE TABLE ops_user_roles (
    id character varying(36) NOT NULL,
    ops_user_id character varying(36) NOT NULL,
    role_code character varying(50) NOT NULL,
    created_by character varying(36),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

-- ops_operations (运维操作记录表)
CREATE TABLE ops_operations (
    id character varying(36) NOT NULL,
    operation_id character varying(64) NOT NULL,
    operator_id character varying(36),
    operator_name character varying(100) NOT NULL,
    target_env character varying(50) NOT NULL,
    target_service character varying(100) NOT NULL,
    cluster_id character varying(100),
    tenant_id character varying(36),
    action character varying(100) NOT NULL,
    resource_type character varying(100),
    resource_id character varying(255),
    request_payload json DEFAULT '{}'::json NOT NULL,
    before_snapshot json,
    after_snapshot json,
    status character varying(20) DEFAULT 'PENDING' NOT NULL,
    error_message text,
    audit_log_id character varying(36),
    approved_by character varying(36),
    approved_at timestamp without time zone,
    review_note text,
    source_ip character varying(64),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    finished_at timestamp without time zone
);

-- ops_task_events (运维任务事件表)
CREATE TABLE ops_task_events (
    id character varying(36) NOT NULL,
    operation_id character varying(64) NOT NULL,
    task_id character varying(100) NOT NULL,
    event_type character varying(20) NOT NULL,
    message text,
    payload json DEFAULT '{}'::json NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    error_code character varying(50),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

-- quota_overrides (配额覆盖表)
CREATE TABLE quota_overrides (
    id character varying(36) NOT NULL,
    tenant_id character varying(36) NOT NULL,
    dimension character varying(50) NOT NULL,
    override_value integer NOT NULL,
    reason text NOT NULL,
    expires_at timestamp without time zone,
    created_by character varying(36),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

-- 自托管开源版不创建支付、订阅销售、人工开通或兑换表。

-- platform_app_configs (平台应用配置表)
CREATE TABLE platform_app_configs (
    id character varying(36) NOT NULL,
    tenant_id uuid NOT NULL,
    platform character varying(20) NOT NULL,
    app_id character varying(255) NOT NULL,
    encrypted_credentials text NOT NULL,
    display_name character varying(100),
    verification_token character varying(255),
    encrypt_key character varying(255),
    is_active boolean DEFAULT true NOT NULL,
    config json DEFAULT '{}'::json,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

-- platform_users (平台用户表)
CREATE TABLE platform_users (
    id integer NOT NULL,
    platform character varying(50) NOT NULL,
    platform_user_id character varying(255) NOT NULL,
    system_user_id character varying(36),
    tenant_id character varying(36),
    display_name character varying(255),
    avatar_url text,
    email character varying(255),
    metadata json DEFAULT '{}'::json,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    app_config_id character varying(36)
);

-- integration_conversations (集成会话表)
CREATE TABLE integration_conversations (
    id integer NOT NULL,
    conversation_id character varying(255) NOT NULL,
    platform character varying(50) NOT NULL,
    platform_user_id character varying(255) NOT NULL,
    system_conversation_id character varying(36),
    tenant_id character varying(36) NOT NULL,
    dataset_id character varying(36),
    context json DEFAULT '[]'::json,
    message_count integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    last_active_at timestamp without time zone DEFAULT now() NOT NULL
);

-- Sequences for auto-increment columns
CREATE SEQUENCE integration_conversations_id_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE platform_users_id_seq START WITH 1 INCREMENT BY 1;

-- ============================================================
-- 主键
-- ============================================================
ALTER TABLE alembic_version ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);
ALTER TABLE tenants ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);
ALTER TABLE users ADD CONSTRAINT users_pkey PRIMARY KEY (id);
ALTER TABLE workspaces ADD CONSTRAINT workspaces_pkey PRIMARY KEY (id);
ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_pkey PRIMARY KEY (id);
ALTER TABLE datasets ADD CONSTRAINT datasets_pkey PRIMARY KEY (id);
ALTER TABLE documents ADD CONSTRAINT documents_pkey PRIMARY KEY (id);
ALTER TABLE document_chunks ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);
ALTER TABLE document_copy_status ADD CONSTRAINT document_copy_status_pkey PRIMARY KEY (id);
ALTER TABLE conversations ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);
ALTER TABLE messages ADD CONSTRAINT messages_pkey PRIMARY KEY (id);
ALTER TABLE oauth_accounts ADD CONSTRAINT oauth_accounts_pkey PRIMARY KEY (id);
ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);
ALTER TABLE api_keys ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);
ALTER TABLE user_configs ADD CONSTRAINT user_configs_pkey PRIMARY KEY (id);
ALTER TABLE user_api_keys ADD CONSTRAINT user_api_keys_pkey PRIMARY KEY (id);
ALTER TABLE login_activities ADD CONSTRAINT login_activities_pkey PRIMARY KEY (id);
ALTER TABLE ops_users ADD CONSTRAINT ops_users_pkey PRIMARY KEY (id);
ALTER TABLE ops_roles ADD CONSTRAINT ops_roles_pkey PRIMARY KEY (id);
ALTER TABLE ops_user_roles ADD CONSTRAINT ops_user_roles_pkey PRIMARY KEY (id);
ALTER TABLE ops_operations ADD CONSTRAINT ops_operations_pkey PRIMARY KEY (id);
ALTER TABLE ops_task_events ADD CONSTRAINT ops_task_events_pkey PRIMARY KEY (id);
ALTER TABLE quota_overrides ADD CONSTRAINT quota_overrides_pkey PRIMARY KEY (id);
ALTER TABLE platform_app_configs ADD CONSTRAINT platform_app_configs_pkey PRIMARY KEY (id);
ALTER TABLE platform_users ADD CONSTRAINT platform_users_pkey PRIMARY KEY (id);
ALTER TABLE integration_conversations ADD CONSTRAINT integration_conversations_pkey PRIMARY KEY (id);

-- ============================================================
-- 唯一约束
-- ============================================================
ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
ALTER TABLE users ADD CONSTRAINT users_username_key UNIQUE (username);
ALTER TABLE document_chunks ADD CONSTRAINT uq_document_chunk UNIQUE (document_id, chunk_index);
ALTER TABLE workspace_members ADD CONSTRAINT uq_workspace_user UNIQUE (workspace_id, user_id);
ALTER TABLE integration_conversations ADD CONSTRAINT uq_integration_conv_lookup UNIQUE (platform, conversation_id);
ALTER TABLE ops_user_roles ADD CONSTRAINT uq_ops_user_role UNIQUE (ops_user_id, role_code);
ALTER TABLE platform_app_configs ADD CONSTRAINT uq_pac_platform_app UNIQUE (platform, app_id);
ALTER TABLE platform_users ADD CONSTRAINT uq_platform_users_lookup UNIQUE (platform, platform_user_id);
ALTER TABLE ops_users ADD CONSTRAINT ops_users_email_key UNIQUE (email);
ALTER TABLE ops_users ADD CONSTRAINT ops_users_username_key UNIQUE (username);
ALTER TABLE ops_roles ADD CONSTRAINT ops_roles_code_key UNIQUE (code);
ALTER TABLE ops_operations ADD CONSTRAINT ops_operations_operation_id_key UNIQUE (operation_id);

-- ============================================================
-- Check 约束
-- ============================================================
ALTER TABLE ops_operations ADD CONSTRAINT chk_ops_operation_status CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'));
ALTER TABLE ops_task_events ADD CONSTRAINT chk_ops_task_event_type CHECK (event_type IN ('DISPATCHED', 'STARTED', 'PROGRESS', 'SUCCEEDED', 'FAILED', 'RETRY'));
ALTER TABLE quota_overrides ADD CONSTRAINT chk_quota_override_dimension CHECK (dimension IN ('users', 'documents', 'storage_mb', 'api_calls_monthly', 'chat_messages_monthly', 'workspaces'));

-- ============================================================
-- 外键
-- ============================================================
ALTER TABLE users ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE users ADD CONSTRAINT users_current_workspace_id_fkey FOREIGN KEY (current_workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL;
ALTER TABLE workspaces ADD CONSTRAINT workspaces_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE datasets ADD CONSTRAINT datasets_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE documents ADD CONSTRAINT documents_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE;
ALTER TABLE document_chunks ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;
ALTER TABLE document_copy_status ADD CONSTRAINT document_copy_status_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE;
ALTER TABLE conversations ADD CONSTRAINT conversations_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE;
ALTER TABLE conversations ADD CONSTRAINT fk_conversation_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE conversations ADD CONSTRAINT fk_conversations_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL;
ALTER TABLE messages ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE;
ALTER TABLE oauth_accounts ADD CONSTRAINT oauth_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;
ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL;
ALTER TABLE api_keys ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_configs ADD CONSTRAINT user_configs_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_api_keys ADD CONSTRAINT user_api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE login_activities ADD CONSTRAINT login_activities_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE ops_users ADD CONSTRAINT ops_users_user_ref_id_fkey FOREIGN KEY (user_ref_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE ops_user_roles ADD CONSTRAINT ops_user_roles_ops_user_id_fkey FOREIGN KEY (ops_user_id) REFERENCES ops_users(id) ON DELETE CASCADE;
ALTER TABLE ops_user_roles ADD CONSTRAINT ops_user_roles_role_code_fkey FOREIGN KEY (role_code) REFERENCES ops_roles(code) ON DELETE CASCADE;
ALTER TABLE ops_user_roles ADD CONSTRAINT ops_user_roles_created_by_fkey FOREIGN KEY (created_by) REFERENCES ops_users(id) ON DELETE SET NULL;
ALTER TABLE quota_overrides ADD CONSTRAINT quota_overrides_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE quota_overrides ADD CONSTRAINT quota_overrides_created_by_fkey FOREIGN KEY (created_by) REFERENCES ops_users(id) ON DELETE SET NULL;
ALTER TABLE platform_app_configs ADD CONSTRAINT fk_pac_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- ============================================================
-- 索引
-- ============================================================
CREATE INDEX idx_tenant_email ON tenants(contact_email);
CREATE INDEX idx_tenant_plan ON tenants(plan);
CREATE INDEX idx_tenant_status ON tenants(status);

CREATE INDEX idx_user_tenant ON users(tenant_id);
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_user_username ON users(username);
CREATE INDEX idx_user_current_workspace ON users(current_workspace_id);

CREATE INDEX idx_workspace_tenant ON workspaces(tenant_id);
CREATE INDEX idx_workspace_name ON workspaces(name);

CREATE INDEX idx_workspace_member_workspace ON workspace_members(workspace_id);
CREATE INDEX idx_workspace_member_user ON workspace_members(user_id);

CREATE INDEX idx_dataset_workspace ON datasets(workspace_id);
CREATE INDEX idx_dataset_name ON datasets(name);

CREATE INDEX idx_document_dataset ON documents(dataset_id);
CREATE INDEX idx_document_status ON documents(status);
CREATE INDEX idx_document_type ON documents(file_type);

CREATE INDEX idx_chunk_document ON document_chunks(document_id);

CREATE INDEX idx_copy_status_dataset ON document_copy_status(dataset_id);
CREATE INDEX idx_copy_status_status ON document_copy_status(status);

CREATE INDEX idx_conversation_dataset ON conversations(dataset_id);
CREATE INDEX idx_conversation_user ON conversations(user_id);
CREATE INDEX idx_conversation_visibility ON conversations(visibility);
CREATE INDEX idx_conversation_workspace_id ON conversations(workspace_id);
CREATE INDEX idx_conversation_user_visibility ON conversations(user_id, visibility);
CREATE INDEX idx_conversation_workspace_visibility ON conversations(workspace_id, visibility);

CREATE INDEX idx_message_conversation ON messages(conversation_id);
CREATE INDEX idx_message_role ON messages(role);

CREATE INDEX idx_oauth_user ON oauth_accounts(user_id);
CREATE INDEX idx_oauth_provider ON oauth_accounts(provider);

CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_tenant_id ON audit_logs(tenant_id);

CREATE INDEX idx_api_key_user ON api_keys(user_id);
CREATE INDEX idx_api_key_hash ON api_keys(key_hash);

CREATE INDEX idx_user_config_user ON user_configs(user_id);

CREATE INDEX idx_user_api_key_user ON user_api_keys(user_id);
CREATE INDEX idx_user_api_key_provider ON user_api_keys(provider);

CREATE INDEX idx_login_activity_user ON login_activities(user_id);
CREATE INDEX idx_login_activity_created ON login_activities(created_at);

CREATE INDEX idx_ops_users_active ON ops_users(is_active);

CREATE INDEX idx_ops_user_roles_user ON ops_user_roles(ops_user_id);

CREATE INDEX idx_ops_operations_status_created ON ops_operations(status, created_at);
CREATE INDEX idx_ops_operations_tenant_action_created ON ops_operations(tenant_id, action, created_at);
CREATE INDEX idx_ops_operations_tenant_status_created ON ops_operations(tenant_id, status, created_at);

CREATE INDEX idx_ops_task_events_created ON ops_task_events(created_at);
CREATE INDEX idx_ops_task_events_operation ON ops_task_events(operation_id);
CREATE INDEX idx_ops_task_events_task_id ON ops_task_events(task_id);

CREATE INDEX idx_quota_overrides_expires_at ON quota_overrides(expires_at);
CREATE INDEX idx_quota_overrides_tenant_dimension ON quota_overrides(tenant_id, dimension);

CREATE INDEX idx_pac_tenant ON platform_app_configs(tenant_id);
CREATE INDEX idx_pac_platform_app ON platform_app_configs(platform, app_id);

CREATE INDEX idx_platform_users_lookup ON platform_users(platform, platform_user_id);
CREATE INDEX idx_platform_users_system ON platform_users(system_user_id);
CREATE INDEX idx_platform_users_tenant ON platform_users(tenant_id);
CREATE INDEX idx_platform_users_app_config ON platform_users(app_config_id);

CREATE INDEX idx_integration_conv_lookup ON integration_conversations(platform, conversation_id);
CREATE INDEX idx_integration_conv_user ON integration_conversations(platform, platform_user_id);

-- Partial unique index for quota_overrides
CREATE UNIQUE INDEX uq_quota_overrides_tenant_dimension_active ON quota_overrides(tenant_id, dimension) WHERE expires_at IS NULL;

-- ============================================================
-- 触发器
-- ============================================================
CREATE TRIGGER trg_ops_operations_updated_at BEFORE UPDATE ON ops_operations FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();
CREATE TRIGGER trg_ops_roles_updated_at BEFORE UPDATE ON ops_roles FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();
CREATE TRIGGER trg_ops_users_updated_at BEFORE UPDATE ON ops_users FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();
CREATE TRIGGER trg_quota_overrides_updated_at BEFORE UPDATE ON quota_overrides FOR EACH ROW EXECUTE FUNCTION set_updated_at_timestamp();

-- ============================================================
-- 序列默认值
-- ============================================================
ALTER TABLE integration_conversations ALTER COLUMN id SET DEFAULT nextval('integration_conversations_id_seq'::regclass);
ALTER TABLE platform_users ALTER COLUMN id SET DEFAULT nextval('platform_users_id_seq'::regclass);
