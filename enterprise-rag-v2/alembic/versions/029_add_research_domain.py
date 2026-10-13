"""Add research projects, runs, sources, evidence, findings and reports."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "029_add_research_domain"
down_revision: Union[str, None] = "028_add_knowledge_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def _common(table: str, uuid_type):
    return [
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workspace_id", uuid_type, sa.ForeignKey("workspaces.id"), nullable=False),
    ]


def upgrade() -> None:
    u = _uuid_type()
    op.create_table(
        "research_projects", *_common("research_projects", u),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("metadata", sa.JSON()), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("deleted_at", sa.DateTime()),
    )
    op.create_index("idx_research_project_workspace", "research_projects", ["workspace_id", "status"])
    op.create_index("idx_research_project_tenant", "research_projects", ["tenant_id"])

    op.create_table(
        "research_questions", *_common("research_questions", u),
        sa.Column("project_id", u, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_question_project", "research_questions", ["project_id", "sort_order"])

    op.create_table(
        "research_samples", *_common("research_samples", u),
        sa.Column("project_id", u, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", u, sa.ForeignKey("assets.id", ondelete="SET NULL")),
        sa.Column("dataset_id", u, sa.ForeignKey("datasets.id", ondelete="SET NULL")),
        sa.Column("source_uri", sa.Text()), sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_sample_project", "research_samples", ["project_id"])

    op.create_table(
        "research_runs", *_common("research_runs", u),
        sa.Column("project_id", u, sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", u, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("plan", sa.JSON()), sa.Column("limits", sa.JSON()), sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stage", sa.String(64)), sa.Column("error_message", sa.Text()), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_run_project_status", "research_runs", ["project_id", "status"])

    op.create_table(
        "research_sources", *_common("research_sources", u),
        sa.Column("run_id", u, sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", u, sa.ForeignKey("assets.id", ondelete="SET NULL")), sa.Column("source_uri", sa.Text()),
        sa.Column("title", sa.String(255)), sa.Column("content_hash", sa.String(64)), sa.Column("status", sa.String(32), nullable=False, server_default="available"), sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_source_run", "research_sources", ["run_id"])

    op.create_table(
        "research_evidence", *_common("research_evidence", u),
        sa.Column("run_id", u, sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("source_id", u, sa.ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False), sa.Column("quote", sa.Text(), nullable=False), sa.Column("locator", sa.String(255)), sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_evidence_run", "research_evidence", ["run_id"])

    op.create_table(
        "research_findings", *_common("research_findings", u),
        sa.Column("run_id", u, sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("claim", sa.Text(), nullable=False), sa.Column("claim_type", sa.String(32), nullable=False, server_default="observation"), sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"), sa.Column("evidence_ids", sa.JSON()), sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"), sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_finding_run", "research_findings", ["run_id"])

    op.create_table(
        "research_reports", *_common("research_reports", u),
        sa.Column("run_id", u, sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("content_markdown", sa.Text(), nullable=False, server_default=""), sa.Column("content_json", sa.JSON()), sa.Column("model_name", sa.String(128)), sa.Column("prompt_version", sa.String(64)), sa.Column("citation_completeness", sa.Float(), nullable=False, server_default="0"), sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"), sa.Column("published_dataset_id", u, sa.ForeignKey("datasets.id", ondelete="SET NULL")), sa.Column("published_document_id", u, sa.ForeignKey("documents.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_research_report_workspace", "research_reports", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_research_report_workspace", table_name="research_reports"); op.drop_table("research_reports")
    op.drop_index("idx_research_finding_run", table_name="research_findings"); op.drop_table("research_findings")
    op.drop_index("idx_research_evidence_run", table_name="research_evidence"); op.drop_table("research_evidence")
    op.drop_index("idx_research_source_run", table_name="research_sources"); op.drop_table("research_sources")
    op.drop_index("idx_research_run_project_status", table_name="research_runs"); op.drop_table("research_runs")
    op.drop_index("idx_research_sample_project", table_name="research_samples"); op.drop_table("research_samples")
    op.drop_index("idx_research_question_project", table_name="research_questions"); op.drop_table("research_questions")
    op.drop_index("idx_research_project_tenant", table_name="research_projects"); op.drop_index("idx_research_project_workspace", table_name="research_projects"); op.drop_table("research_projects")
