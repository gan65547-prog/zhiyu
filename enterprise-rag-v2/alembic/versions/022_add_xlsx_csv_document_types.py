"""Add XLSX, XLS, CSV document types

Revision ID: 022_add_xlsx_csv_document_types
Revises: 021_add_work_orders_and_instances
Create Date: 2026-05-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '022_add_xlsx_csv_document_types'
down_revision: Union[str, None] = '017_add_users_current_workspace_id'
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

            for label in ('XLSX', 'XLS', 'CSV'):
                if label not in existing_labels:
                    op.execute(f"ALTER TYPE documenttype ADD VALUE '{label}'")
        except Exception:
            pass
    else:
        pass


def downgrade() -> None:
    pass
