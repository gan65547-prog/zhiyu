"""audit_logs 补齐与 ORM / 内部运维查询一致的列

Revision ID: 011_audit_logs_align_orm
Revises: 010_add_ops_updated_at_triggers
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "011_audit_logs_align_orm"
down_revision = "010_add_ops_updated_at_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 004 仅含 id/tenant_id/action/details/ip/user_agent/request_id/created_at
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("audit_logs")}

    if "resource_type" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("resource_type", sa.String(length=50), nullable=True),
        )
    if "resource_id" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("resource_id", sa.String(length=255), nullable=True),
        )
    if "user_id" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("user_id", sa.String(length=36), nullable=True),
        )
    if "workspace_id" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
        )
    if "status" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("status", sa.String(length=20), nullable=True, server_default="success"),
        )
    if "error_message" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("error_message", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("audit_logs")}
    for name in (
        "error_message",
        "status",
        "workspace_id",
        "user_id",
        "resource_id",
        "resource_type",
    ):
        if name in cols:
            op.drop_column("audit_logs", name)
