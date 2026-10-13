"""Add persisted Agent schedules."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "032_add_agent_schedules"
down_revision: Union[str, None] = "031_add_research_knowledge_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    u = _uuid_type()
    op.create_table(
        "agent_schedules",
        sa.Column("id", u, primary_key=True),
        sa.Column("tenant_id", u, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", u, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("definition_id", u, sa.ForeignKey("agent_definitions.id"), nullable=False),
        sa.Column("project_id", u, sa.ForeignKey("research_projects.id"), nullable=False),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("schedule_expression", sa.String(128), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("last_run_at", sa.DateTime()),
        sa.Column("last_run_id", u, sa.ForeignKey("research_runs.id", ondelete="SET NULL")),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_agent_schedule_due", "agent_schedules", ["enabled", "next_run_at"])
    op.create_index("idx_agent_schedule_workspace", "agent_schedules", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_agent_schedule_workspace", table_name="agent_schedules")
    op.drop_index("idx_agent_schedule_due", table_name="agent_schedules")
    op.drop_table("agent_schedules")
