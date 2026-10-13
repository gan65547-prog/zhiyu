"""Map assets to an optional legacy Dataset for compatibility ingestion."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "027_add_asset_dataset_mapping"
down_revision: Union[str, None] = "026_add_asset_storage_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    dataset_type = (
        postgresql.UUID(as_uuid=True)
        if op.get_bind().dialect.name == "postgresql"
        else sa.String(36)
    )
    dataset_column = sa.Column("dataset_id", dataset_type, nullable=True)
    if not is_sqlite:
        dataset_column.append_foreign_key(
            sa.ForeignKey("datasets.id", ondelete="SET NULL")
        )
    op.add_column("assets", dataset_column)
    op.create_index("idx_asset_dataset", "assets", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("idx_asset_dataset", table_name="assets")
    op.drop_column("assets", "dataset_id")
