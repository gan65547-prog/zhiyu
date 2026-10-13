"""add updated_at triggers for ops tables

Revision ID: 010_add_ops_updated_at_triggers
Revises: 009_add_quota_overrides_active_unique_index
Create Date: 2026-04-18

包含：
- set_updated_at_timestamp() 函数
- trg_ops_users_updated_at 触发器
- trg_ops_roles_updated_at 触发器
- trg_ops_operations_updated_at 触发器
- trg_quota_overrides_updated_at 触发器

所有触发器都使用 IF NOT EXISTS 方式创建，支持重复运行。
"""

from alembic import op


revision = "010_add_ops_updated_at_triggers"
down_revision = "009_add_quota_overrides_active_unique_index"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # SQLite 没有 PostgreSQL 的函数/触发器语法。开发环境和轻量级回归
    # 使用 SQLite 时，直接用同等语义的行级触发器维护 updated_at，避免
    # `alembic upgrade head` 在迁移 010 处中断。
    if bind.dialect.name == "sqlite":
        for table in ("ops_users", "ops_roles", "ops_operations", "quota_overrides"):
            trigger = f"trg_{table}_updated_at"
            op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
            op.execute(
                f"""
                CREATE TRIGGER {trigger}
                AFTER UPDATE ON {table}
                FOR EACH ROW
                WHEN NEW.updated_at = OLD.updated_at
                BEGIN
                    UPDATE {table}
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = OLD.id;
                END
                """
            )
        return

    # 创建函数（使用 CREATE OR REPLACE 确保幂等性）
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # 创建触发器（使用 DROP IF EXISTS 确保幂等性）
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_ops_users_updated_at ON ops_users
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ops_users_updated_at
        BEFORE UPDATE ON ops_users
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at_timestamp()
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_ops_roles_updated_at ON ops_roles
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ops_roles_updated_at
        BEFORE UPDATE ON ops_roles
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at_timestamp()
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_ops_operations_updated_at ON ops_operations
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ops_operations_updated_at
        BEFORE UPDATE ON ops_operations
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at_timestamp()
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_quota_overrides_updated_at ON quota_overrides
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_quota_overrides_updated_at
        BEFORE UPDATE ON quota_overrides
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at_timestamp()
        """
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        for table in ("ops_users", "ops_roles", "ops_operations", "quota_overrides"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at")
        return

    # 删除触发器（使用 IF EXISTS 确保幂等性）
    op.execute("DROP TRIGGER IF EXISTS trg_quota_overrides_updated_at ON quota_overrides")
    op.execute("DROP TRIGGER IF EXISTS trg_ops_operations_updated_at ON ops_operations")
    op.execute("DROP TRIGGER IF EXISTS trg_ops_roles_updated_at ON ops_roles")
    op.execute("DROP TRIGGER IF EXISTS trg_ops_users_updated_at ON ops_users")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at_timestamp()")
