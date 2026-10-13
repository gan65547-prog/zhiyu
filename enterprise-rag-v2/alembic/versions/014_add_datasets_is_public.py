"""Add datasets.is_public column

Revision ID: 014_add_datasets_is_public
Revises: 013_merge_branches
Create Date: 2026-04-20

datasets 表缺少 is_public 列，ORM 模型有该字段但迁移未同步。
使用 inspect 检查后再添加，保证幂等性。
"""

from alembic import op
import sqlalchemy as sa

revision = "014_add_datasets_is_public"
down_revision = "013_merge_branches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 检查 datasets 表是否存在
    if not insp.has_table("datasets"):
        return

    cols = {c["name"] for c in insp.get_columns("datasets")}

    if "is_public" not in cols:
        op.add_column(
            "datasets",
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("datasets")}
    if "is_public" in cols:
        op.drop_column("datasets", "is_public")
