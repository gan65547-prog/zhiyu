"""Add deterministic content retrospective records."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "035_add_content_retrospectives"
down_revision: Union[str, None] = "034_add_content_publish_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    u = _uuid_type()
    op.create_table("content_retrospectives", sa.Column("id", u, primary_key=True), sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False), sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False), sa.Column("publish_record_id", u, sa.ForeignKey("content_publish_records.id", ondelete="CASCADE"), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("recommendations", sa.JSON(), nullable=False), sa.Column("metric_snapshot", sa.JSON(), nullable=False), sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("idx_content_retro_publish", "content_retrospectives", ["publish_record_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_content_retro_publish", table_name="content_retrospectives"); op.drop_table("content_retrospectives")
