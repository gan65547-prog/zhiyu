"""Allow research usage dimensions in tenant quota overrides."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "036_add_research_quota_dimensions"
down_revision: Union[str, None] = "035_add_content_retrospectives"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DIMENSIONS = (
    "'users', 'documents', 'storage_mb', 'api_calls_monthly', 'chat_messages_monthly', 'workspaces', "
    "'research_runs_monthly', 'research_sources_monthly', 'research_output_tokens_monthly'"
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    constraints = {item.get("name") for item in inspect(bind).get_check_constraints("quota_overrides")}
    if "chk_quota_override_dimension" in constraints:
        op.drop_constraint("chk_quota_override_dimension", "quota_overrides", type_="check")
    op.create_check_constraint(
        "chk_quota_override_dimension",
        "quota_overrides",
        f"dimension IN ({_DIMENSIONS})",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    constraints = {item.get("name") for item in inspect(bind).get_check_constraints("quota_overrides")}
    if "chk_quota_override_dimension" in constraints:
        op.drop_constraint("chk_quota_override_dimension", "quota_overrides", type_="check")
    op.create_check_constraint(
        "chk_quota_override_dimension",
        "quota_overrides",
        "dimension IN ('users', 'documents', 'storage_mb', 'api_calls_monthly', 'chat_messages_monthly', 'workspaces')",
    )
