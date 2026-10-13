"""Add beginner-friendly ingestion batches."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "044_add_ingestion_batches"
down_revision: Union[str, None] = "043_add_user_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    u = _uuid_type()
    if "ingestion_batches" not in tables:
        op.create_table(
            "ingestion_batches",
            sa.Column("id", u, primary_key=True),
            sa.Column("tenant_id", u, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("dataset_id", u, sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by", u, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
            sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("options_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("idx_ingestion_batch_workspace", "ingestion_batches", ["workspace_id", "created_at"])
        op.create_index("idx_ingestion_batch_status", "ingestion_batches", ["workspace_id", "status"])
    asset_columns = {column["name"] for column in sa.inspect(bind).get_columns("assets")}
    if "batch_id" not in asset_columns:
        batch_id = sa.Column("batch_id", u, nullable=True)
        if bind.dialect.name == "sqlite":
            # SQLite cannot ALTER TABLE ... ADD CONSTRAINT.  Batch mode rebuilds
            # the table while preserving the existing columns and constraints,
            # which keeps the full migration chain testable on SQLite.
            with op.batch_alter_table("assets", recreate="always") as batch_op:
                batch_op.add_column(batch_id)
                batch_op.create_foreign_key(
                    "fk_assets_batch_id", "ingestion_batches", ["batch_id"], ["id"], ondelete="SET NULL"
                )
        else:
            op.add_column("assets", batch_id)
            op.create_foreign_key("fk_assets_batch_id", "assets", "ingestion_batches", ["batch_id"], ["id"], ondelete="SET NULL")
        op.create_index("idx_asset_batch", "assets", ["batch_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "assets" in sa.inspect(bind).get_table_names():
        indexes = {item["name"] for item in sa.inspect(bind).get_indexes("assets")}
        if "idx_asset_batch" in indexes:
            op.drop_index("idx_asset_batch", table_name="assets")
        fks = {item.get("name") for item in sa.inspect(bind).get_foreign_keys("assets")}
        has_batch_id = "batch_id" in {column["name"] for column in sa.inspect(bind).get_columns("assets")}
        if bind.dialect.name == "sqlite" and has_batch_id:
            with op.batch_alter_table("assets", recreate="always") as batch_op:
                if "fk_assets_batch_id" in fks:
                    batch_op.drop_constraint("fk_assets_batch_id", type_="foreignkey")
                batch_op.drop_column("batch_id")
        else:
            if "fk_assets_batch_id" in fks:
                op.drop_constraint("fk_assets_batch_id", "assets", type_="foreignkey")
            if has_batch_id:
                op.drop_column("assets", "batch_id")
    if "ingestion_batches" in sa.inspect(bind).get_table_names():
        op.drop_index("idx_ingestion_batch_status", table_name="ingestion_batches")
        op.drop_index("idx_ingestion_batch_workspace", table_name="ingestion_batches")
        op.drop_table("ingestion_batches")
