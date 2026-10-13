"""add partial unique index for active quota overrides

Revision ID: 009_add_quota_overrides_active_unique_index
Revises: 008_add_ops_center_tables
Create Date: 2026-04-17
"""

from alembic import op


revision = "009_add_quota_overrides_active_unique_index"
down_revision = "008a_widen_alembic_version_num"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_quota_overrides_tenant_dimension_active
        ON quota_overrides (tenant_id, dimension)
        WHERE expires_at IS NULL
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_quota_overrides_tenant_dimension_active")
