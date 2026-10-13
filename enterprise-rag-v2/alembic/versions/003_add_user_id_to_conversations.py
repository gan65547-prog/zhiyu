"""Add user_id column to conversations table

Revision ID: 003_add_user_id_to_conversations
Revises: 002_add_epub_document_type
Create Date: 2026-04-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003_add_user_id_to_conversations'
down_revision: Union[str, None] = '002_add_epub_document_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if user_id column already exists before adding
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("conversations")}

    # 根据数据库类型选择合适的 UUID 列类型（与 users.id 保持一致）
    from alembic.context import get_context
    ctx = get_context()
    if ctx.dialect.name == 'postgresql':
        user_id_col = sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True)
    else:
        user_id_col = sa.Column('user_id', sa.String(36), nullable=True)

    # 使用batch mode添加user_id列到conversations表（SQLite兼容）
    with op.batch_alter_table('conversations') as batch_op:
        if 'user_id' not in cols:
            batch_op.add_column(user_id_col)

        # 添加外键约束（检查是否已存在）
        fks = {fk['name'] for fk in insp.get_foreign_keys('conversations')}
        if 'fk_conversation_user' not in fks:
            try:
                batch_op.create_foreign_key('fk_conversation_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')
            except Exception:
                pass  # Foreign key already exists or creation failed

        # 添加索引（检查是否已存在）
        idxs = {idx['name'] for idx in insp.get_indexes('conversations')}
        if 'idx_conversation_user' not in idxs:
            try:
                batch_op.create_index('idx_conversation_user', ['user_id'])
            except Exception:
                pass  # Index already exists or creation failed

def downgrade() -> None:
    # 使用batch mode删除user_id列（SQLite兼容）
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("conversations")}
    
    with op.batch_alter_table('conversations') as batch_op:
        # 删除索引
        try:
            batch_op.drop_index('idx_conversation_user')
        except:
            pass
        
        # 删除外键约束
        try:
            batch_op.drop_constraint('fk_conversation_user', type_='foreignkey')
        except:
            pass
        
        # 删除user_id列
        if 'user_id' in cols:
            batch_op.drop_column('user_id')
