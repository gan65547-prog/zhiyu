"""Add document_errata table

Revision ID: 024_add_document_errata
Revises: 023_add_knowledge_type
Create Date: 2026-05-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '024_add_document_errata'
down_revision: Union[str, None] = '023_add_knowledge_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # sa.Enum with create_type=True (default) handles enum creation via IF NOT EXISTS
        op.create_table(
            'document_errata',
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('errata_code', sa.String(20), nullable=False, unique=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=False),
            sa.Column('severity', sa.Enum('critical', 'major', 'minor', 'note', name='errataseverity'), nullable=False),
            sa.Column('status', sa.Enum('open', 'in_progress', 'resolved', 'closed', name='erratastatus'), nullable=False),
            sa.Column('fix_suggestion', sa.Text, nullable=True),
            sa.Column('source_evidence', sa.Text, nullable=True),
            sa.Column('affected_document_ids', sa.JSON, default=list),
            sa.Column('related_document_ids', sa.JSON, default=list),
            sa.Column('reported_by', sa.String(100), nullable=True),
            sa.Column('resolved_at', sa.DateTime, nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.Column('updated_at', sa.DateTime, nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_errata_severity', 'document_errata', ['severity'])
        op.create_index('idx_errata_status', 'document_errata', ['status'])
        op.create_index('idx_errata_code', 'document_errata', ['errata_code'])
    else:
        # SQLite
        op.create_table(
            'document_errata',
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('errata_code', sa.String(20), nullable=False, unique=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=False),
            sa.Column('severity', sa.String(20), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('fix_suggestion', sa.Text, nullable=True),
            sa.Column('source_evidence', sa.Text, nullable=True),
            sa.Column('affected_document_ids', sa.JSON, default=list),
            sa.Column('related_document_ids', sa.JSON, default=list),
            sa.Column('reported_by', sa.String(100), nullable=True),
            sa.Column('resolved_at', sa.DateTime, nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.Column('updated_at', sa.DateTime, nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_errata_severity', 'document_errata', ['severity'])
        op.create_index('idx_errata_status', 'document_errata', ['status'])
        op.create_index('idx_errata_code', 'document_errata', ['errata_code'])


def downgrade() -> None:
    op.drop_table('document_errata')
