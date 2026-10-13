"""add ops center core tables

Revision ID: 008_add_ops_center_tables
Revises: 007_add_platform_app_configs
Create Date: 2026-04-17

包含：
- ops_users 表（运维用户表）
- ops_roles 表（运维角色表）
- ops_user_roles 表（用户角色关联表）
- ops_operations 表（操作审计表）
- ops_task_events 表（任务事件表）
- quota_overrides 表（配额覆盖表）

所有表都添加了幂等性检查，支持重复运行。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from uuid import uuid4


revision = "008_add_ops_center_tables"
down_revision = "007_add_platform_app_configs"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    timestamp_default = sa.text("NOW()" if bind.dialect.name == "postgresql" else "CURRENT_TIMESTAMP")

    # ========== 1. ops_users 表 ==========
    if 'ops_users' not in existing_tables:
        op.create_table(
            "ops_users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("username", sa.String(50), nullable=False, unique=True),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("user_ref_id", sa.String(36), nullable=True),  # 关联users.id（应用层关联，不加FK因类型不兼容）
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            # 注意：不添加user_ref_id→users.id的外键，因为String(36)无法引用UUID类型
        )
        op.create_index("idx_ops_users_active", "ops_users", ["is_active"])

    # ========== 2. ops_roles 表 ==========
    if 'ops_roles' not in existing_tables:
        op.create_table(
            "ops_roles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
        )

    # ========== 3. ops_user_roles 表 ==========
    if 'ops_user_roles' not in existing_tables:
        op.create_table(
            "ops_user_roles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("ops_user_id", sa.String(36), nullable=False),
            sa.Column("role_code", sa.String(50), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.ForeignKeyConstraint(["ops_user_id"], ["ops_users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["role_code"], ["ops_roles.code"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["ops_users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("ops_user_id", "role_code", name="uq_ops_user_role"),
        )
        op.create_index("idx_ops_user_roles_user", "ops_user_roles", ["ops_user_id"])

    # ========== 4. ops_operations 表 ==========
    if 'ops_operations' not in existing_tables:
        op.create_table(
            "ops_operations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("operation_id", sa.String(64), nullable=False, unique=True),
            sa.Column("operator_id", sa.String(36), nullable=True),
            sa.Column("operator_name", sa.String(100), nullable=False),
            sa.Column("target_env", sa.String(50), nullable=False),
            sa.Column("target_service", sa.String(100), nullable=False),
            sa.Column("cluster_id", sa.String(100), nullable=True),
            sa.Column("tenant_id", sa.String(36), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("resource_type", sa.String(100), nullable=True),
            sa.Column("resource_id", sa.String(255), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("before_snapshot", sa.JSON(), nullable=True),
            sa.Column("after_snapshot", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("audit_log_id", sa.String(36), nullable=True),
            sa.Column("approved_by", sa.String(36), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("source_ip", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            # 注意：不添加audit_log_id→audit_logs.id的外键（audit_logs在后续迁移创建，且类型可能不兼容）
            sa.CheckConstraint(
                "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
                name="chk_ops_operation_status",
            ),
        )
        op.create_index("idx_ops_operations_tenant_status_created", "ops_operations", ["tenant_id", "status", "created_at"])
        op.create_index("idx_ops_operations_tenant_action_created", "ops_operations", ["tenant_id", "action", "created_at"])
        op.create_index("idx_ops_operations_status_created", "ops_operations", ["status", "created_at"])

    # ========== 5. ops_task_events 表 ==========
    if 'ops_task_events' not in existing_tables:
        op.create_table(
            "ops_task_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("operation_id", sa.String(64), nullable=False),
            sa.Column("task_id", sa.String(100), nullable=False),
            sa.Column("event_type", sa.String(20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.CheckConstraint(
                "event_type IN ('DISPATCHED', 'STARTED', 'PROGRESS', 'SUCCEEDED', 'FAILED', 'RETRY')",
                name="chk_ops_task_event_type",
            ),
        )
        op.create_index("idx_ops_task_events_operation", "ops_task_events", ["operation_id"])
        op.create_index("idx_ops_task_events_task_id", "ops_task_events", ["task_id"])
        op.create_index("idx_ops_task_events_created", "ops_task_events", ["created_at"])

    # ========== 6. quota_overrides 表 ==========
    if 'quota_overrides' not in existing_tables:
        op.create_table(
            "quota_overrides",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False),
            sa.Column("dimension", sa.String(50), nullable=False),
            sa.Column("override_value", sa.Integer(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=timestamp_default),
            # 注意：不添加tenant_id→tenants.id的外键（String(36)无法引用UUID类型）
            sa.ForeignKeyConstraint(["created_by"], ["ops_users.id"], ondelete="SET NULL"),
            sa.CheckConstraint(
                "dimension IN ('users', 'documents', 'storage_mb', 'api_calls_monthly', 'chat_messages_monthly', 'workspaces')",
                name="chk_quota_override_dimension",
            ),
        )
        op.create_index("idx_quota_overrides_tenant_dimension", "quota_overrides", ["tenant_id", "dimension"])
        op.create_index("idx_quota_overrides_expires_at", "quota_overrides", ["expires_at"])

    # ========== 7. 插入默认角色数据（仅当表刚创建时）==========
    if 'ops_roles' in inspector.get_table_names():
        # 检查是否已有数据
        from sqlalchemy import text as sa_text
        result = bind.execute(sa_text("SELECT COUNT(*) FROM ops_roles"))
        if result.scalar() == 0:
            roles = [
                ("super_admin", "超级管理员", "平台级全权限"),
                ("tenant_ops", "租户运维", "租户与配额运维"),
                ("read_only_auditor", "审计只读", "仅查看审计与报表"),
            ]
            for code, name, description in roles:
                bind.execute(sa_text(
                    "INSERT INTO ops_roles (id, code, name, description) VALUES (:id, :code, :name, :description) ON CONFLICT (code) DO NOTHING"
                ), {"id": str(uuid4()), "code": code, "name": name, "description": description})
            bind.commit()


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # 按逆序删除表和索引（带检查）
    if 'quota_overrides' in existing_tables:
        op.drop_index("idx_quota_overrides_expires_at", table_name="quota_overrides")
        op.drop_index("idx_quota_overrides_tenant_dimension", table_name="quota_overrides")
        op.drop_table("quota_overrides")

    if 'ops_task_events' in existing_tables:
        op.drop_index("idx_ops_task_events_created", table_name="ops_task_events")
        op.drop_index("idx_ops_task_events_task_id", table_name="ops_task_events")
        op.drop_index("idx_ops_task_events_operation", table_name="ops_task_events")
        op.drop_table("ops_task_events")

    if 'ops_operations' in existing_tables:
        op.drop_index("idx_ops_operations_status_created", table_name="ops_operations")
        op.drop_index("idx_ops_operations_tenant_action_created", table_name="ops_operations")
        op.drop_index("idx_ops_operations_tenant_status_created", table_name="ops_operations")
        op.drop_table("ops_operations")

    if 'ops_user_roles' in existing_tables:
        op.drop_index("idx_ops_user_roles_user", table_name="ops_user_roles")
        op.drop_table("ops_user_roles")

    if 'ops_roles' in existing_tables:
        op.drop_table("ops_roles")

    if 'ops_users' in existing_tables:
        op.drop_index("idx_ops_users_active", table_name="ops_users")
        op.drop_table("ops_users")
