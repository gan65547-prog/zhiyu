"""Add conversation permissions (visibility and workspace_id)

Revision ID: 006_add_conversation_permissions
Revises: 005_add_integration_tables
Create Date: 2026-04-06

This migration adds:
1. visibility column (private/workspace/tenant) to conversations table
2. workspace_id column for workspace-based permission filtering
3. Performance indexes for permission queries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging

logger = logging.getLogger(__name__)

revision = '006_add_conversation_permissions'
down_revision = '005_add_integration_tables'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add conversation permissions fields and indexes
    
    Changes:
    - Add visibility VARCHAR(20) NOT NULL DEFAULT 'private'
    - Add workspace_id VARCHAR(36) nullable
    - Create indexes for performance optimization
    - Backfill workspace_id from datasets table
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("conversations")}

    # 根据数据库类型选择 UUID 类型（与 workspaces.id 保持一致）
    from alembic.context import get_context
    ctx = get_context()
    if ctx.dialect.name == 'postgresql':
        workspace_id_type = postgresql.UUID(as_uuid=True)
    else:
        workspace_id_type = sa.String(36)

    # 1. Add visibility column with default value 'private'
    if 'visibility' not in cols:
        logger.info("Adding visibility column...")
        op.add_column(
            'conversations',
            sa.Column(
                'visibility',
                sa.String(20),
                nullable=False,
                server_default='private',
                comment='Conversation visibility: private|workspace|tenant'
            )
        )

    # 2. Add workspace_id column (nullable)，类型与 workspaces.id 一致
    if 'workspace_id' not in cols:
        logger.info("Adding workspace_id column...")
        op.add_column(
            'conversations',
            sa.Column(
                'workspace_id',
                workspace_id_type,
                nullable=True,
                comment='Workspace ID for permission filtering'
            )
        )

    # 3. Add foreign key constraint（仅当约束不存在时）
    fks = {fk['name'] for fk in insp.get_foreign_keys('conversations')}
    if 'fk_conversations_workspace' not in fks:
        logger.info("Adding foreign key constraint...")
        try:
            op.create_foreign_key(
                'fk_conversations_workspace',
                'conversations',
                'workspaces',
                ['workspace_id'], ['id'],
                ondelete='SET NULL'
            )
        except Exception:
            pass  # Foreign key already exists
    
    # 4. Create indexes for performance (check if they don't exist)
    logger.info("Creating indexes...")
    indexes = {idx['name'] for idx in insp.get_indexes("conversations")}
    
    if 'idx_conversations_visibility' not in indexes:
        op.create_index(
            'idx_conversations_visibility',
            'conversations',
            ['visibility']
        )
    
    if 'idx_conversations_workspace_id' not in indexes:
        op.create_index(
            'idx_conversations_workspace_id',
            'conversations',
            ['workspace_id']
        )
    
    if 'idx_conversations_user_visibility' not in indexes:
        op.create_index(
            'idx_conversations_user_visibility',
            'conversations',
            ['user_id', 'visibility']
        )
    
    if 'idx_conversations_workspace_visibility' not in indexes:
        op.create_index(
            'idx_conversations_workspace_visibility',
            'conversations',
            ['workspace_id', 'visibility']
        )
    
    logger.info("Migration completed successfully!")


def downgrade():
    """Remove conversation permissions fields and indexes"""
    logger.info("Rolling back conversation permissions migration...")
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("conversations")}
    indexes = {idx['name'] for idx in insp.get_indexes("conversations")}

    # Drop indexes
    if 'idx_conversations_workspace_visibility' in indexes:
        op.drop_index('idx_conversations_workspace_visibility', 'conversations')
    if 'idx_conversations_user_visibility' in indexes:
        op.drop_index('idx_conversations_user_visibility', 'conversations')
    if 'idx_conversations_workspace_id' in indexes:
        op.drop_index('idx_conversations_workspace_id', 'conversations')
    if 'idx_conversations_visibility' in indexes:
        op.drop_index('idx_conversations_visibility', 'conversations')
    
    # Drop foreign key
    try:
        op.drop_constraint('fk_conversations_workspace', 'conversations', type_='foreignkey')
    except:
        pass
    
    # Drop columns
    if 'workspace_id' in cols:
        op.drop_column('conversations', 'workspace_id')
    if 'visibility' in cols:
        op.drop_column('conversations', 'visibility')
    
    logger.info("Rollback completed successfully!")
