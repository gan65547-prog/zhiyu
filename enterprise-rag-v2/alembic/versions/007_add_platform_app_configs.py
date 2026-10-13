"""add platform_app_configs table for multi-tenant platform routing

Revision ID: 007_add_platform_app_configs
Revises: 006_add_conversation_permissions
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '007_add_platform_app_configs'
down_revision = '006_add_conversation_permissions'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()
    timestamp_default = sa.text("NOW()" if bind.dialect.name == "postgresql" else "CURRENT_TIMESTAMP")
    
    # Create platform_app_configs table if it doesn't exist
    if 'platform_app_configs' not in tables:
        # 根据数据库类型选择 UUID 列类型
        from alembic.context import get_context
        ctx = get_context()
        if ctx.dialect.name == 'postgresql':
            tenant_id_col = sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False,
                                      comment='关联tenants.id')
        else:
            tenant_id_col = sa.Column('tenant_id', sa.String(36), nullable=False,
                                      comment='关联tenants.id')

        op.create_table(
            'platform_app_configs',
            sa.Column('id', sa.String(36), primary_key=True),
            tenant_id_col,
            sa.Column('platform', sa.String(20), nullable=False,
                      comment='平台: feishu|wecom|dingtalk'),
            sa.Column('app_id', sa.String(255), nullable=False,
                      comment='各平台的 app_id / corp_id'),
            sa.Column('encrypted_credentials', sa.Text(), nullable=False,
                      comment='Fernet加密的凭证JSON'),
            sa.Column('display_name', sa.String(100), nullable=True,
                      comment='显示名称'),
            sa.Column('verification_token', sa.String(255), nullable=True,
                      comment='飞书/企微 webhook验证token'),
            sa.Column('encrypt_key', sa.String(255), nullable=True,
                      comment='飞书加解密key'),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('TRUE')),
            sa.Column('config', sa.JSON(), nullable=True,
                      server_default=sa.text("'{}'")),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default,
                      nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=timestamp_default,
                      nullable=False),

            sa.UniqueConstraint('platform', 'app_id',
                                 name='uq_pac_platform_app'),

            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'],
                                    name='fk_pac_tenant',
                                    ondelete='CASCADE'),
        )

        op.create_index('idx_pac_platform_app', 'platform_app_configs',
                         ['platform', 'app_id'], unique=True)
        op.create_index('idx_pac_tenant', 'platform_app_configs', ['tenant_id'])
    
    # Add app_config_id column to platform_users if it doesn't exist
    if 'platform_users' in tables:
        platform_users_cols = {c["name"] for c in insp.get_columns("platform_users")}
        
        if 'app_config_id' not in platform_users_cols:
            op.add_column('platform_users',
                          sa.Column('app_config_id', sa.String(36), nullable=True,
                                    comment='关联platform_app_configs.id'))
        
        # Create index if it doesn't exist
        platform_users_indexes = {idx['name'] for idx in insp.get_indexes("platform_users")}
        if 'idx_platform_users_app_config' not in platform_users_indexes:
            op.create_index('idx_platform_users_app_config', 'platform_users',
                             ['app_config_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # Check platform_users table exists before modifying
    if 'platform_users' in tables:
        platform_users_indexes = {idx['name'] for idx in insp.get_indexes("platform_users")}
        platform_users_cols = {c["name"] for c in insp.get_columns("platform_users")}
        
        if 'idx_platform_users_app_config' in platform_users_indexes:
            op.drop_index('idx_platform_users_app_config',
                           table_name='platform_users')
        
        if 'app_config_id' in platform_users_cols:
            op.drop_column('platform_users', 'app_config_id')
    
    # Drop platform_app_configs table if it exists
    if 'platform_app_configs' in tables:
        op.drop_index('idx_pac_tenant', table_name='platform_app_configs')
        op.drop_index('idx_pac_platform_app', table_name='platform_app_configs')
        op.drop_table('platform_app_configs')
