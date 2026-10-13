"""Add EPUB document type

Revision ID: 002_add_epub_document_type
Revises: 001_initial_schema
Create Date: 2026-04-04

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '002_add_epub_document_type'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        try:
            existing_values = bind.execute(
                sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'documenttype'::regtype")
            ).fetchall()
            existing_labels = {row[0] for row in existing_values}

            if 'EPUB' not in existing_labels:
                op.execute("ALTER TYPE documenttype ADD VALUE 'EPUB'")
        except Exception:
            pass
    else:
        pass


def downgrade() -> None:
    pass
