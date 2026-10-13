"""Add durable storage metadata for unified assets."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "026_add_asset_storage_fields"
down_revision: Union[str, None] = "025_add_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("storage_key", sa.String(512), nullable=True))
    op.add_column("assets", sa.Column("source_etag", sa.String(255), nullable=True))
    op.create_index("idx_asset_storage_key", "assets", ["storage_key"])


def downgrade() -> None:
    op.drop_index("idx_asset_storage_key", table_name="assets")
    op.drop_column("assets", "source_etag")
    op.drop_column("assets", "storage_key")
