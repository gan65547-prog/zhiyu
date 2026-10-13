"""Add the AI workbench unified assets table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "025_add_assets"
down_revision: Union[str, None] = "024_add_document_errata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_column(name: str, foreign_key: str | None = None, nullable: bool = False):
    if op.get_bind().dialect.name == "postgresql":
        column_type = postgresql.UUID(as_uuid=True)
    else:
        column_type = sa.String(36)
    if foreign_key:
        return sa.Column(name, column_type, sa.ForeignKey(foreign_key, ondelete="CASCADE"), nullable=nullable)
    return sa.Column(name, column_type, nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        asset_id = sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()"))
        legacy_document_id = sa.Column("legacy_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    else:
        asset_id = sa.Column("id", sa.String(36), primary_key=True)
        legacy_document_id = sa.Column("legacy_document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    op.create_table(
        "assets",
        asset_id,
        _uuid_column("tenant_id", "tenants.id"),
        _uuid_column("workspace_id", "workspaces.id"),
        _uuid_column("created_by", "users.id"),
        legacy_document_id,
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("mime_type", sa.String(127), nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("legacy_document_id", name="uq_asset_legacy_document"),
    )
    op.create_index("idx_asset_tenant_workspace", "assets", ["tenant_id", "workspace_id"])
    op.create_index("idx_asset_workspace_status", "assets", ["workspace_id", "status"])
    op.create_index("idx_asset_content_hash", "assets", ["content_hash"])
    op.create_index("idx_asset_created_by", "assets", ["created_by"])


def downgrade() -> None:
    op.drop_index("idx_asset_created_by", table_name="assets")
    op.drop_index("idx_asset_content_hash", table_name="assets")
    op.drop_index("idx_asset_workspace_status", table_name="assets")
    op.drop_index("idx_asset_tenant_workspace", table_name="assets")
    op.drop_table("assets")
