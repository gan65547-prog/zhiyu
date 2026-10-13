"""Persist reading desk notes and understanding annotations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "042_add_document_annotations"
down_revision: Union[str, None] = "041_add_content_metric_sync_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_annotations" in inspector.get_table_names():
        return
    u = postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)
    op.create_table(
        "document_annotations",
        sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, nullable=False),
        sa.Column("workspace_id", u, nullable=False),
        sa.Column("document_id", u, nullable=False),
        sa.Column("author_id", u, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="note"),
        sa.Column("quote", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_document_annotation_document", "document_annotations", ["document_id", "created_at"])
    op.create_index("idx_document_annotation_workspace", "document_annotations", ["workspace_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if "document_annotations" in sa.inspect(bind).get_table_names():
        op.drop_index("idx_document_annotation_workspace", table_name="document_annotations")
        op.drop_index("idx_document_annotation_document", table_name="document_annotations")
        op.drop_table("document_annotations")
