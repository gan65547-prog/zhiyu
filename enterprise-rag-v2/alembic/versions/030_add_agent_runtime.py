"""Add explicit agent workflow runtime tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "030_add_agent_runtime"
down_revision: Union[str, None] = "029_add_research_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def _common(uuid_type):
    return [
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", uuid_type, sa.ForeignKey("workspaces.id"), nullable=False),
    ]


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    u = _uuid_type()
    op.create_table(
        "agent_definitions", *_common(u),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("workflow", sa.JSON(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_agent_definition_workspace", "agent_definitions", ["workspace_id", "status"])
    op.create_table(
        "agent_runs", *_common(u),
        sa.Column("definition_id", u, sa.ForeignKey("agent_definitions.id"), nullable=False),
        sa.Column("research_run_id", u, sa.ForeignKey("research_runs.id", ondelete="SET NULL")),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("input_json", sa.JSON(), nullable=False), sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.String(64)), sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_agent_run_workspace_status", "agent_runs", ["workspace_id", "status"])
    if is_sqlite:
        op.create_index("uq_agent_run_research_run", "agent_runs", ["research_run_id"], unique=True)
    else:
        op.create_unique_constraint("uq_agent_run_research_run", "agent_runs", ["research_run_id"])
    op.create_table(
        "agent_run_steps", *_common(u),
        sa.Column("agent_run_id", u, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(64), nullable=False), sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("input_json", sa.JSON(), nullable=False), sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("agent_run_id", "step_key", name="uq_agent_run_step_key"),
    )
    op.create_index("idx_agent_step_run_order", "agent_run_steps", ["agent_run_id", "step_order"])
    op.create_table(
        "agent_outputs", *_common(u),
        sa.Column("agent_run_id", u, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", u, sa.ForeignKey("agent_run_steps.id", ondelete="SET NULL")),
        sa.Column("output_type", sa.String(64), nullable=False), sa.Column("title", sa.String(255)),
        sa.Column("content_text", sa.Text()), sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"), sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_agent_output_run", "agent_outputs", ["agent_run_id"])
    op.create_table(
        "agent_approvals", *_common(u),
        sa.Column("agent_run_id", u, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", u, sa.ForeignKey("agent_run_steps.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", u, sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("reviewed_at", sa.DateTime()),
    )
    op.create_index("idx_agent_approval_run_status", "agent_approvals", ["agent_run_id", "status"])


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    op.drop_index("idx_agent_approval_run_status", table_name="agent_approvals"); op.drop_table("agent_approvals")
    op.drop_index("idx_agent_output_run", table_name="agent_outputs"); op.drop_table("agent_outputs")
    op.drop_index("idx_agent_step_run_order", table_name="agent_run_steps"); op.drop_table("agent_run_steps")
    if is_sqlite:
        op.drop_index("uq_agent_run_research_run", table_name="agent_runs")
    else:
        op.drop_constraint("uq_agent_run_research_run", "agent_runs", type_="unique")
    op.drop_index("idx_agent_run_workspace_status", table_name="agent_runs"); op.drop_table("agent_runs")
    op.drop_index("idx_agent_definition_workspace", table_name="agent_definitions"); op.drop_table("agent_definitions")
