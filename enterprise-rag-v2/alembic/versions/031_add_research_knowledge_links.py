"""Link approved research reports and evidence into the knowledge center."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "031_add_research_knowledge_links"
down_revision: Union[str, None] = "030_add_agent_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    return postgresql.UUID(as_uuid=True) if op.get_bind().dialect.name == "postgresql" else sa.String(36)


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    u = _uuid_type()
    op.add_column("research_reports", sa.Column("published_knowledge_item_id", u, nullable=True))
    if not is_sqlite:
        op.create_foreign_key(
            "fk_research_report_knowledge_item", "research_reports", "knowledge_items",
            ["published_knowledge_item_id"], ["id"], ondelete="SET NULL",
        )
    op.add_column("knowledge_evidence", sa.Column("research_evidence_id", u, nullable=True))
    if not is_sqlite:
        op.create_foreign_key(
            "fk_knowledge_evidence_research_evidence", "knowledge_evidence", "research_evidence",
            ["research_evidence_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if not is_sqlite:
        op.drop_constraint("fk_knowledge_evidence_research_evidence", "knowledge_evidence", type_="foreignkey")
    op.drop_column("knowledge_evidence", "research_evidence_id")
    if not is_sqlite:
        op.drop_constraint("fk_research_report_knowledge_item", "research_reports", type_="foreignkey")
    op.drop_column("research_reports", "published_knowledge_item_id")
