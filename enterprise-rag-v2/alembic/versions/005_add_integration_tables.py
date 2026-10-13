"""add integration tables for OpenClaw hybrid architecture

Revision ID: 005_add_integration_tables
Revises: 004_mvp_commercialization
Create Date: 2026-04-06

包含：
- platform_users 表（平台用户映射表）
- integration_conversations 表（集成会话表）

所有表都添加了幂等性检查，支持重复运行。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '005_add_integration_tables'
down_revision = '004_mvp_commercialization'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    timestamp_default = sa.text("NOW()" if bind.dialect.name == "postgresql" else "CURRENT_TIMESTAMP")

    # ===========================================
    # 1. platform_users 表 (平台用户映射表)
    # ===========================================
    if 'platform_users' not in existing_tables:
        op.create_table(
            'platform_users',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),

            # 平台信息
            sa.Column('platform', sa.String(50), nullable=False, comment='平台: feishu|wecom|wechat|qq|dingtalk'),
            sa.Column('platform_user_id', sa.String(255), nullable=False, comment='平台唯一ID'),

            # 系统映射（Integer引用UUID，无法做FK约束，仅作应用层关联）
            sa.Column('system_user_id', sa.String(36), nullable=True, comment='关联users.id（UUID字符串）'),
            sa.Column('tenant_id', sa.String(36), nullable=True, comment='关联tenants.id（UUID字符串）'),

            # 用户信息缓存
            sa.Column('display_name', sa.String(255), nullable=True, comment='显示名称'),
            sa.Column('avatar_url', sa.Text(), nullable=True, comment='头像URL'),
            sa.Column('email', sa.String(255), nullable=True, comment='邮箱'),
            sa.Column('metadata', sa.JSON(), nullable=True, server_default=sa.text("'{}'"), comment='额外信息'),

            # 时间戳
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=timestamp_default, nullable=False),

            # 唯一约束: 同一平台的同一用户只能有一条记录
            sa.UniqueConstraint('platform', 'platform_user_id', name='uq_platform_users_lookup'),
            # 注意：不添加外键约束，因为 system_user_id/tenant_id 是 String 引用 UUID 主键
        )

        # 创建索引
        op.create_index('idx_platform_users_lookup', 'platform_users', ['platform', 'platform_user_id'])
        op.create_index('idx_platform_users_system', 'platform_users', ['system_user_id'])
        op.create_index('idx_platform_users_tenant', 'platform_users', ['tenant_id'])

    # ===========================================
    # 2. integration_conversations 表 (集成会话表)
    # ===========================================
    if 'integration_conversations' not in existing_tables:
        op.create_table(
            'integration_conversations',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),

            # 会话标识
            sa.Column('conversation_id', sa.String(255), nullable=False, comment='平台会话ID'),
            sa.Column('platform', sa.String(50), nullable=False, comment='平台'),
            sa.Column('platform_user_id', sa.String(255), nullable=False, comment='平台用户ID'),

            # 系统关联（String引用UUID，应用层关联，无FK约束）
            sa.Column('system_conversation_id', sa.String(36), nullable=True, comment='关联conversations.id（UUID字符串）'),
            sa.Column('tenant_id', sa.String(36), nullable=False, comment='租户ID（UUID字符串）'),
            sa.Column('dataset_id', sa.String(36), nullable=True, comment='默认查询的知识库ID（UUID字符串）'),

            # 会话上下文
            sa.Column('context', sa.JSON(), nullable=True, server_default=sa.text("'[]'"), comment='对话历史'),
            sa.Column('message_count', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='消息计数'),

            # 时间戳
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.Column('last_active_at', sa.DateTime(), server_default=timestamp_default, nullable=False),

            # 唯一约束: 同一平台的同一会话只能有一条记录
            sa.UniqueConstraint('platform', 'conversation_id', name='uq_integration_conv_lookup'),
            # 注意：不添加外键约束，UUID类型不兼容
        )

        # 创建索引
        op.create_index('idx_integration_conv_lookup', 'integration_conversations', ['platform', 'conversation_id'])
        op.create_index('idx_integration_conv_user', 'integration_conversations', ['platform', 'platform_user_id'])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # 删除表和索引（带检查）
    if 'integration_conversations' in existing_tables:
        op.drop_index('idx_integration_conv_user', table_name='integration_conversations')
        op.drop_index('idx_integration_conv_lookup', table_name='integration_conversations')
        op.drop_table('integration_conversations')

    if 'platform_users' in existing_tables:
        op.drop_index('idx_platform_users_tenant', table_name='platform_users')
        op.drop_index('idx_platform_users_system', table_name='platform_users')
        op.drop_index('idx_platform_users_lookup', table_name='platform_users')
        op.drop_table('platform_users')
