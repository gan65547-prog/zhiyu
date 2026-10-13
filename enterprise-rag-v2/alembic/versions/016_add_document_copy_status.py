"""Add document_copy_status table

Revision ID: 016_add_document_copy_status
Revises: 015_add_workspace_is_default
Create Date: 2026-04-20

添加文档复制状态追踪表，用于记录文档复制任务的状态和进度。
使用 inspect 检查后再创建，保证幂等性。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016_add_document_copy_status"
down_revision = "015_add_workspace_is_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()
    is_postgresql = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)
    timestamp_default = sa.text("NOW()" if is_postgresql else "CURRENT_TIMESTAMP")

    if "datasets" not in tables:
        return

    if "document_copy_status" not in tables:
        id_col = sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("uuid_generate_v4()") if is_postgresql else None)
        dataset_id_col = sa.Column("dataset_id", uuid_type, nullable=False)
        op.create_table(
            "document_copy_status",
            id_col,
            dataset_id_col,
            sa.Column("task_id", sa.String(length=255), nullable=True),
            sa.Column("total_documents", sa.Integer(), nullable=True, default=0),
            sa.Column("completed_documents", sa.Integer(), nullable=True, default=0),
            sa.Column("failed_documents", sa.Integer(), nullable=True, default=0),
            sa.Column("status", sa.String(length=50), nullable=True, default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id")
        )
        op.create_index(op.f("idx_copy_status_dataset"), "document_copy_status", ["dataset_id"], unique=False)
        op.create_index(op.f("idx_copy_status_status"), "document_copy_status", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()
    if "document_copy_status" in tables:
        op.drop_table("document_copy_status")
