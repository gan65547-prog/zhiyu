"""Initial schema migration

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 只在PostgreSQL中创建UUID扩展
    from sqlalchemy import text
    from alembic.context import get_context
    
    context = get_context()
    is_postgresql = context.dialect.name == 'postgresql'
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)
    json_type = postgresql.JSON if is_postgresql else sa.JSON
    timestamp_default = sa.text('NOW()' if is_postgresql else 'CURRENT_TIMESTAMP')
    if is_postgresql:
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # 根据数据库类型选择合适的UUID类型和默认值
    from alembic.context import get_context
    
    context = get_context()
    if is_postgresql:
        id_column = sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()'))
    else:
        # SQLite使用String类型存储UUID
        id_column = sa.Column('id', sa.String(36), primary_key=True)
    
    op.create_table(
        'tenants',
        id_column,
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=False),
        sa.Column('contact_phone', sa.String(50)),
        sa.Column('plan', sa.Enum('FREE', 'BASIC', 'PRO', 'ENTERPRISE', name='subscriptionplan'), nullable=False, server_default='FREE'),
        sa.Column('status', sa.Enum('ACTIVE', 'SUSPENDED', 'DELETED', name='tenantstatus'), nullable=False, server_default='ACTIVE'),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_tenant_status', 'tenants', ['status'])
    op.create_index('idx_tenant_plan', 'tenants', ['plan'])
    op.create_index('idx_tenant_email', 'tenants', ['contact_email'])

    # 创建users表
    if is_postgresql:
        user_id_column = sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()'))
        user_tenant_id_column = sa.Column('tenant_id', uuid_type, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    else:
        user_id_column = sa.Column('id', sa.String(36), primary_key=True)
        user_tenant_id_column = sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    op.create_table(
        'users',
        user_id_column,
        user_tenant_id_column,
        sa.Column('username', sa.String(50), nullable=False, unique=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_user_tenant', 'users', ['tenant_id'])
    op.create_index('idx_user_email', 'users', ['email'])
    op.create_index('idx_user_username', 'users', ['username'])

    # 创建workspaces表
    if is_postgresql:
        workspace_id_column = sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()'))
        workspace_tenant_id_column = sa.Column('tenant_id', uuid_type, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    else:
        workspace_id_column = sa.Column('id', sa.String(36), primary_key=True)
        workspace_tenant_id_column = sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    op.create_table(
        'workspaces',
        workspace_id_column,
        workspace_tenant_id_column,
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_workspace_tenant', 'workspaces', ['tenant_id'])
    op.create_index('idx_workspace_name', 'workspaces', ['name'])

    # 创建workspace_members表
    if is_postgresql:
        workspace_member_id_column = sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()'))
        workspace_member_workspace_id_column = sa.Column('workspace_id', uuid_type, sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
        workspace_member_user_id_column = sa.Column('user_id', uuid_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    else:
        workspace_member_id_column = sa.Column('id', sa.String(36), primary_key=True)
        workspace_member_workspace_id_column = sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
        workspace_member_user_id_column = sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    op.create_table(
        'workspace_members',
        workspace_member_id_column,
        workspace_member_workspace_id_column,
        workspace_member_user_id_column,
        sa.Column('role', sa.Enum('OWNER', 'ADMIN', 'MEMBER', 'VIEWER', name='workspacerole'), nullable=False, server_default='MEMBER'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
    )
    op.create_index('idx_workspace_member_workspace', 'workspace_members', ['workspace_id'])
    op.create_index('idx_workspace_member_user', 'workspace_members', ['user_id'])

    op.create_table(
        'datasets',
        sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()') if is_postgresql else None),
        sa.Column('workspace_id', uuid_type, sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('embedding_model', sa.String(255), nullable=False),
        sa.Column('chunk_size', sa.Integer, nullable=False, server_default='500'),
        sa.Column('chunk_overlap', sa.Integer, nullable=False, server_default='50'),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_dataset_workspace', 'datasets', ['workspace_id'])
    op.create_index('idx_dataset_name', 'datasets', ['name'])

    op.create_table(
        'documents',
        sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()') if is_postgresql else None),
        sa.Column('dataset_id', uuid_type, sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_type', sa.Enum('PDF', 'DOCX', 'TXT', 'MD', 'HTML', name='documenttype'), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='documentstatus'), nullable=False, server_default='PENDING'),
        sa.Column('tags', json_type, server_default='[]'),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('chunk_count', sa.Integer, server_default='0'),
        sa.Column('indexed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_document_dataset', 'documents', ['dataset_id'])
    op.create_index('idx_document_status', 'documents', ['status'])
    op.create_index('idx_document_type', 'documents', ['file_type'])

    op.create_table(
        'document_chunks',
        sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()') if is_postgresql else None),
        sa.Column('document_id', uuid_type, sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunk'),
    )
    op.create_index('idx_chunk_document', 'document_chunks', ['document_id'])

    op.create_table(
        'conversations',
        sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()') if is_postgresql else None),
        sa.Column('dataset_id', uuid_type, sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255)),
        sa.Column('metadata', json_type, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_conversation_dataset', 'conversations', ['dataset_id'])

    op.create_table(
        'messages',
        sa.Column('id', uuid_type, primary_key=True, server_default=sa.text('uuid_generate_v4()') if is_postgresql else None),
        sa.Column('conversation_id', uuid_type, sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('retrieved_chunks', json_type),
        sa.Column('tokens_used', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index('idx_message_conversation', 'messages', ['conversation_id'])
    op.create_index('idx_message_role', 'messages', ['role'])


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('datasets')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
    op.drop_table('users')
    op.drop_table('tenants')

    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS documentstatus')
        op.execute('DROP TYPE IF EXISTS documenttype')
        op.execute('DROP TYPE IF EXISTS workspacerole')
        op.execute('DROP TYPE IF EXISTS tenantstatus')
        op.execute('DROP TYPE IF EXISTS subscriptionplan')
