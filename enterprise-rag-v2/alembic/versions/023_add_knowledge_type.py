"""Add knowledge_type column to documents

Revision ID: 023_add_knowledge_type
Revises: 022_add_learning_diagnosis_tables
Create Date: 2026-05-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '023_add_knowledge_type'
down_revision: Union[str, None] = '022_add_learning_diagnosis_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.execute("""
            DO $$ BEGIN
                CREATE TYPE knowledgetype AS ENUM (
                    'topic', 'concept', 'summary', 'recipe', 'reference', 'errata'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """)
        op.add_column('documents',
            sa.Column('knowledge_type', sa.Enum(
                'topic', 'concept', 'summary', 'recipe', 'reference', 'errata',
                name='knowledgetype'
            ), nullable=True))
        op.create_index('idx_document_knowledge_type', 'documents', ['knowledge_type'])
    else:
        # SQLite: use VARCHAR instead of enum
        op.add_column('documents',
            sa.Column('knowledge_type', sa.String(20), nullable=True))
        op.create_index('idx_document_knowledge_type', 'documents', ['knowledge_type'])


def downgrade() -> None:
    op.drop_index('idx_document_knowledge_type', 'documents')
    op.drop_column('documents', 'knowledge_type')
