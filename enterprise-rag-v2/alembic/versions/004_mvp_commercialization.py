"""Create the shared audit log table; legacy commercial tables are omitted.

Revision ID: 004_mvp_commercialization
Revises: 003_add_user_id_to_conversations
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "004_mvp_commercialization"
down_revision = "003_add_user_id_to_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the shared audit table required by later migrations."""
    bind = op.get_bind()
    if "audit_logs" in inspect(bind).get_table_names():
        return
    uuid_type = postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)
    op.create_table(
        "audit_logs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), default=datetime.now(timezone.utc), index=True),
    )
    op.create_index("idx_audit_logs_action_time", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    """Remove the shared audit table when downgrading this revision."""
    if "audit_logs" in inspect(op.get_bind()).get_table_names():
        op.drop_table("audit_logs")
