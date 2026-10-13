"""Fix opsquotadimension enum - add missing api_calls_monthly value

Revision ID: 011_fix_opsquotadimension_enum
Revises: 010_add_ops_updated_at_triggers
Create Date: 2026-04-20

The quota_overrides.dimension column was manually created as a PostgreSQL ENUM type
'opsquotadimension' outside of alembic, which is inconsistent with the VARCHAR(50) +
CheckConstraint approach in migration 008. This migration adds the missing
'api_calls_monthly' enum value that was introduced in the ORM models but never
added to the manually-created enum type.
"""
from alembic import op
import sqlalchemy as sa

revision = "011_fix_opsquotadimension_enum"
down_revision = "011_audit_logs_align_orm"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Only applicable for PostgreSQL
    if dialect != 'postgresql':
        return

    # 检查 opsquotadimension ENUM 类型是否存在（不使用 ::regtype 避免异常污染事务）
    result = bind.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'opsquotadimension' AND typtype = 'e'"
    )).fetchone()

    if result is None:
        # ENUM 类型不存在（migration 008 使用了 VARCHAR + CheckConstraint 方式），无需修复
        return

    existing_values = bind.execute(
        sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'opsquotadimension'::regtype")
    ).fetchall()
    existing_labels = {row[0] for row in existing_values}

    all_expected = {"users", "documents", "storage_mb", "api_calls_monthly", "chat_messages_monthly", "workspaces"}
    missing = all_expected - existing_labels

    for val in sorted(missing):
        # ALTER TYPE ... ADD VALUE 不能在事务中执行（PostgreSQL 限制），需要 COMMIT 前执行
        bind.execute(sa.text(f"ALTER TYPE opsquotadimension ADD VALUE IF NOT EXISTS '{val}'"))


def downgrade():
    pass
