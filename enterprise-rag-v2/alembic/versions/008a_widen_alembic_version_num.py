"""Widen Alembic's version column before long revision ids are applied.

The default Alembic bootstrap creates ``alembic_version.version_num`` as
``VARCHAR(32)``.  Revision 009 is longer than that limit, so the column must
be widened before Alembic attempts to record revision 009.
"""

from alembic import op
import sqlalchemy as sa


revision = "008a_widen_alembic_version_num"
down_revision = "008_add_ops_center_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite treats VARCHAR length as advisory and does not support ALTER
    # COLUMN TYPE; its version_num column is already unbounded in practice.
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=128),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
