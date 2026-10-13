"""Add immutable knowledge item content snapshots for rollback."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision: str = "037_add_knowledge_item_versions"
down_revision: Union[str, None] = "036_add_research_quota_dimensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    u = _uuid_type()
    bind = op.get_bind()
    inspector = inspect(bind)
    if "knowledge_item_versions" in inspector.get_table_names():
        if "idx_knowledge_item_version_item" not in {idx["name"] for idx in inspector.get_indexes("knowledge_item_versions")}:
            op.create_index("idx_knowledge_item_version_item", "knowledge_item_versions", ["knowledge_item_id", "version"])
        return
    op.create_table(
        "knowledge_item_versions",
        sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("knowledge_item_id", u, sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("conclusions", sa.JSON()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("knowledge_item_id", "version", name="uq_knowledge_item_version"),
    )
    op.create_index("idx_knowledge_item_version_item", "knowledge_item_versions", ["knowledge_item_id", "version"])


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "knowledge_item_versions" not in inspector.get_table_names():
        return
    if "idx_knowledge_item_version_item" in {idx["name"] for idx in inspector.get_indexes("knowledge_item_versions")}:
        op.drop_index("idx_knowledge_item_version_item", table_name="knowledge_item_versions")
    op.drop_table("knowledge_item_versions")
