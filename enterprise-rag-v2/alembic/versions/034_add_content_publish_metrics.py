"""Add content publish records and metrics."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "034_add_content_publish_metrics"
down_revision: Union[str, None] = "033_add_content_center"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    u = _uuid_type()
    op.create_table("content_publish_records", sa.Column("id", u, primary_key=True), sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False), sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False), sa.Column("draft_id", u, sa.ForeignKey("content_drafts.id", ondelete="CASCADE"), nullable=False), sa.Column("platform", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="published"), sa.Column("external_id", sa.String(255)), sa.Column("published_at", sa.DateTime(), nullable=False), sa.Column("response_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("idx_content_publish_draft", "content_publish_records", ["draft_id"])
    op.create_index("idx_content_publish_workspace", "content_publish_records", ["workspace_id"])
    op.create_table("content_metrics", sa.Column("id", u, primary_key=True), sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False), sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False), sa.Column("publish_record_id", u, sa.ForeignKey("content_publish_records.id", ondelete="CASCADE"), nullable=False), sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"), sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"), sa.Column("likes", sa.Integer(), nullable=False, server_default="0"), sa.Column("comments", sa.Integer(), nullable=False, server_default="0"), sa.Column("shares", sa.Integer(), nullable=False, server_default="0"), sa.Column("raw_json", sa.JSON(), nullable=False), sa.Column("collected_at", sa.DateTime(), nullable=False))
    op.create_index("idx_content_metric_publish", "content_metrics", ["publish_record_id", "collected_at"])


def downgrade() -> None:
    op.drop_index("idx_content_metric_publish", table_name="content_metrics"); op.drop_table("content_metrics")
    op.drop_index("idx_content_publish_workspace", table_name="content_publish_records"); op.drop_index("idx_content_publish_draft", table_name="content_publish_records"); op.drop_table("content_publish_records")
