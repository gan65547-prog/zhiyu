"""Align the Dataset ORM contract with existing databases."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "039_align_dataset_type"
down_revision: Union[str, None] = "038_add_knowledge_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("datasets")}
    if "dataset_type" not in columns:
        op.add_column(
            "datasets",
            sa.Column("dataset_type", sa.String(20), nullable=False, server_default="GENERAL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("datasets")}
    if "dataset_type" in columns:
        op.drop_column("datasets", "dataset_type")
