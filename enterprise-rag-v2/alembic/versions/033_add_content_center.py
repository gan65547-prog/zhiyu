"""Add content topics and drafts for the AI workbench."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "033_add_content_center"
down_revision: Union[str, None] = "032_add_agent_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    u = _uuid_type()
    op.create_table(
        "content_topics", sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("brief", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("tags", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_content_topic_workspace_status", "content_topics", ["workspace_id", "status"])
    op.create_table(
        "content_drafts", sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("topic_id", u, sa.ForeignKey("content_topics.id", ondelete="SET NULL")),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"), sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", u, sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_content_draft_workspace_review", "content_drafts", ["workspace_id", "review_status"])


def downgrade() -> None:
    op.drop_index("idx_content_draft_workspace_review", table_name="content_drafts"); op.drop_table("content_drafts")
    op.drop_index("idx_content_topic_workspace_status", table_name="content_topics"); op.drop_table("content_topics")
