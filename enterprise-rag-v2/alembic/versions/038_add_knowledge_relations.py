"""Add explicit knowledge graph relations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "038_add_knowledge_relations"
down_revision: Union[str, None] = "037_add_knowledge_item_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "knowledge_relations" in inspector.get_table_names():
        existing = {item["name"] for item in inspector.get_indexes("knowledge_relations")}
        for name, columns in (
            ("idx_knowledge_relation_workspace", ["workspace_id", "created_at"]),
            ("idx_knowledge_relation_source", ["source_item_id"]),
            ("idx_knowledge_relation_target", ["target_item_id"]),
        ):
            if name not in existing:
                op.create_index(name, "knowledge_relations", columns)
        return
    u = _uuid_type()
    op.create_table(
        "knowledge_relations",
        sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_item_id", u, sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_item_id", u, sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", u, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_item_id", "target_item_id", "relation_type", name="uq_knowledge_relation_edge"),
    )
    op.create_index("idx_knowledge_relation_workspace", "knowledge_relations", ["workspace_id", "created_at"])
    op.create_index("idx_knowledge_relation_source", "knowledge_relations", ["source_item_id"])
    op.create_index("idx_knowledge_relation_target", "knowledge_relations", ["target_item_id"])


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "knowledge_relations" not in inspector.get_table_names():
        return
    for index in ("idx_knowledge_relation_target", "idx_knowledge_relation_source", "idx_knowledge_relation_workspace"):
        if index in {item["name"] for item in inspector.get_indexes("knowledge_relations")}:
            op.drop_index(index, table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
