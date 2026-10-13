"""Add reviewable knowledge items and traceable evidence bindings."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "028_add_knowledge_items"
down_revision: Union[str, None] = "027_add_asset_dataset_mapping"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()
    op.create_table(
        "knowledge_items",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", uuid_type, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False, server_default="concept"),
        sa.Column("definition", sa.Text(), nullable=False, server_default=""),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("conclusions", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("reviewer_id", uuid_type, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_knowledge_item_workspace_status", "knowledge_items", ["workspace_id", "review_status"])
    op.create_index("idx_knowledge_item_tenant", "knowledge_items", ["tenant_id"])
    op.create_index("idx_knowledge_item_created_at", "knowledge_items", ["created_at"])

    op.create_table(
        "knowledge_evidence",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", uuid_type, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("knowledge_item_id", uuid_type, sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", uuid_type, sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_id", uuid_type, sa.ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("locator", sa.String(255), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_knowledge_evidence_item", "knowledge_evidence", ["knowledge_item_id"])
    op.create_index("idx_knowledge_evidence_asset", "knowledge_evidence", ["asset_id"])
    op.create_index("idx_knowledge_evidence_document", "knowledge_evidence", ["document_id"])


def downgrade() -> None:
    op.drop_index("idx_knowledge_evidence_document", table_name="knowledge_evidence")
    op.drop_index("idx_knowledge_evidence_asset", table_name="knowledge_evidence")
    op.drop_index("idx_knowledge_evidence_item", table_name="knowledge_evidence")
    op.drop_table("knowledge_evidence")
    op.drop_index("idx_knowledge_item_created_at", table_name="knowledge_items")
    op.drop_index("idx_knowledge_item_tenant", table_name="knowledge_items")
    op.drop_index("idx_knowledge_item_workspace_status", table_name="knowledge_items")
    op.drop_table("knowledge_items")
