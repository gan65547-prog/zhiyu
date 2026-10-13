"""Add workspace.is_default column

Revision ID: 015_add_workspace_is_default
Revises: 014_add_datasets_is_public
Create Date: 2026-04-20

workspace 表需要 is_default 列来标记默认工作空间。
使用 inspect 检查后再添加，保证幂等性。
"""

from alembic import op
import sqlalchemy as sa

revision = "015_add_workspace_is_default"
down_revision = "014_add_datasets_is_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 检查 workspaces 表是否存在
    if not insp.has_table("workspaces"):
        return

    cols = {c["name"] for c in insp.get_columns("workspaces")}

    if "is_default" not in cols:
        op.add_column(
            "workspaces",
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("workspaces")}
    if "is_default" in cols:
        op.drop_column("workspaces", "is_default")