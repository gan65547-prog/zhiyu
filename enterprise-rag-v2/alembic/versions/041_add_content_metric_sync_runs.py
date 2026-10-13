"""Persist asynchronous platform metric snapshot sync runs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "041_add_content_metric_sync_runs"
down_revision: Union[str, None] = "040_add_content_connector_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "content_metric_sync_runs" in inspector.get_table_names():
        return
    u = postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)
    op.create_table(
        "content_metric_sync_runs",
        sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, nullable=False),
        sa.Column("workspace_id", u, nullable=False),
        sa.Column("credential_id", u, nullable=True),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("requested_by", u, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["content_connector_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_content_metric_sync_workspace", "content_metric_sync_runs", ["workspace_id", "created_at"])
    op.create_index("idx_content_metric_sync_status", "content_metric_sync_runs", ["status", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if "content_metric_sync_runs" in sa.inspect(bind).get_table_names():
        op.drop_index("idx_content_metric_sync_status", table_name="content_metric_sync_runs")
        op.drop_index("idx_content_metric_sync_workspace", table_name="content_metric_sync_runs")
        op.drop_table("content_metric_sync_runs")
