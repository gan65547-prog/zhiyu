"""add current_workspace_id to users table

Revision ID: 017_add_users_current_workspace_id
Revises: 016_add_document_copy_status
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '017_add_users_current_workspace_id'
down_revision: Union[str, None] = '016_add_document_copy_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot add a column with a new FK constraint using ALTER
        # TABLE. Keep the same nullable identifier and index; FK enforcement
        # remains available for schemas created from the ORM metadata.
        op.add_column('users', sa.Column('current_workspace_id', sa.String(36), nullable=True))
        op.create_index('idx_user_current_workspace', 'users', ['current_workspace_id'])
        return

    op.add_column('users', sa.Column(
        'current_workspace_id',
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True
    ))
    op.create_index('idx_user_current_workspace', 'users', ['current_workspace_id'])


def downgrade() -> None:
    op.drop_index('idx_user_current_workspace', table_name='users')
    op.drop_column('users', 'current_workspace_id')
