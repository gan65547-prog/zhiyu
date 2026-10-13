-- ============================================================
-- 预生产环境增量 DDL
-- 用途：在预生产环境创建缺失的表
-- 执行：ssh $STAGING_HOST 后执行
-- ============================================================

-- 1. oauth_accounts (OAuth账户表) - 预生产缺失
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
ALTER TABLE oauth_accounts ADD CONSTRAINT oauth_accounts_pkey PRIMARY KEY (id);
ALTER TABLE oauth_accounts ADD CONSTRAINT oauth_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_oauth_user ON oauth_accounts(user_id);
CREATE INDEX idx_oauth_provider ON oauth_accounts(provider);

-- 2. api_keys (API密钥表) - 预生产缺失
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
ALTER TABLE api_keys ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);
ALTER TABLE api_keys ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_api_key_user ON api_keys(user_id);
CREATE INDEX idx_api_key_hash ON api_keys(key_hash);

-- 3. user_configs (用户配置表) - 预生产缺失
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
ALTER TABLE user_configs ADD CONSTRAINT user_configs_pkey PRIMARY KEY (id);
ALTER TABLE user_configs ADD CONSTRAINT user_configs_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_user_config_user ON user_configs(user_id);

-- 4. user_api_keys (用户API密钥表) - 预生产缺失
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
ALTER TABLE user_api_keys ADD CONSTRAINT user_api_keys_pkey PRIMARY KEY (id);
ALTER TABLE user_api_keys ADD CONSTRAINT user_api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_user_api_key_user ON user_api_keys(user_id);
CREATE INDEX idx_user_api_key_provider ON user_api_keys(provider);

-- 5. login_activities (登录活动表) - 预生产缺失
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
ALTER TABLE login_activities ADD CONSTRAINT login_activities_pkey PRIMARY KEY (id);
ALTER TABLE login_activities ADD CONSTRAINT login_activities_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_login_activity_user ON login_activities(user_id);
CREATE INDEX idx_login_activity_created ON login_activities(created_at);

-- 商业订阅、订单和兑换表不属于自托管开源部署，不在本脚本中创建。

-- ============================================================
-- 验证
-- ============================================================
-- 执行完成后验证：
-- SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;
-- 应该有 31 个表
