-- ============================================================
-- 修复远端数据库 opsquotadimension 枚举缺失值
-- 直接在 PostgreSQL 中执行（不是通过 alembic）
-- ============================================================
--
-- 背景：
--   quota_overrides.dimension 列被手动创建为 PostgreSQL ENUM 类型 'opsquotadimension'
--   但 alembic 迁移 008 是用 VARCHAR(50) + CheckConstraint 方式。
--   数据库中的枚举缺少 'api_calls_monthly'，导致每次 API 调用都 500。
--
-- 执行方法（在远端 PostgreSQL 中）:
--   psql -U postgres -d <your_database> -f /tmp/fix_opsquotadimension_enum.sql
--
-- 或直接连接数据库执行下面的 SQL。

-- 1. 先确认当前枚举有哪些值
SELECT enumlabel
FROM pg_enum
WHERE enumtypid = 'opsquotadimension'::regtype
ORDER BY enumsortorder;

-- 2. 添加所有缺失的枚举值
-- 注意：PostgreSQL 13+ 支持在事务中执行，但为保险起见建议单独执行
ALTER TYPE opsquotadimension ADD VALUE 'api_calls_monthly';
ALTER TYPE opsquotadimension ADD VALUE 'chat_messages_monthly';

-- 3. 再次确认
SELECT enumlabel
FROM pg_enum
WHERE enumtypid = 'opsquotadimension'::regtype
ORDER BY enumsortorder;
