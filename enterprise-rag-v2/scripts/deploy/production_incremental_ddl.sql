-- ============================================================
-- 生产环境增量 DDL
-- 用途：在生产环境创建缺失的 3 个表
-- 安全：只添加表，不影响现有数据
-- ============================================================

-- 1. platform_app_configs (平台应用配置表)
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
ALTER TABLE platform_app_configs ADD CONSTRAINT platform_app_configs_pkey PRIMARY KEY (id);
ALTER TABLE platform_app_configs ADD CONSTRAINT uq_pac_platform_app UNIQUE (platform, app_id);
ALTER TABLE platform_app_configs ADD CONSTRAINT fk_pac_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX idx_pac_tenant ON platform_app_configs(tenant_id);
CREATE INDEX idx_pac_platform_app ON platform_app_configs(platform, app_id);

-- 2. platform_users (平台用户表)
CREATE SEQUENCE platform_users_id_seq START WITH 1 INCREMENT BY 1;
CREATE TABLE platform_users (
    id integer NOT NULL DEFAULT nextval('platform_users_id_seq'::regclass),
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
ALTER TABLE platform_users ADD CONSTRAINT platform_users_pkey PRIMARY KEY (id);
ALTER TABLE platform_users ADD CONSTRAINT uq_platform_users_lookup UNIQUE (platform, platform_user_id);
CREATE INDEX idx_platform_users_lookup ON platform_users(platform, platform_user_id);
CREATE INDEX idx_platform_users_system ON platform_users(system_user_id);
CREATE INDEX idx_platform_users_tenant ON platform_users(tenant_id);
CREATE INDEX idx_platform_users_app_config ON platform_users(app_config_id);

-- 3. integration_conversations (集成会话表)
CREATE SEQUENCE integration_conversations_id_seq START WITH 1 INCREMENT BY 1;
CREATE TABLE integration_conversations (
    id integer NOT NULL DEFAULT nextval('integration_conversations_id_seq'::regclass),
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
ALTER TABLE integration_conversations ADD CONSTRAINT integration_conversations_pkey PRIMARY KEY (id);
ALTER TABLE integration_conversations ADD CONSTRAINT uq_integration_conv_lookup UNIQUE (platform, conversation_id);
CREATE INDEX idx_integration_conv_lookup ON integration_conversations(platform, conversation_id);
CREATE INDEX idx_integration_conv_user ON integration_conversations(platform, platform_user_id);

-- ============================================================
-- 验证
-- ============================================================
-- 执行完成后验证：
-- SELECT count(*) FROM pg_tables WHERE schemaname='public';
-- 应该有 31 个表