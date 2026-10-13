"""Add user preferences and encrypted API-key storage tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "043_add_user_preferences"
down_revision: Union[str, None] = "042_add_document_annotations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    uuid_type = postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)

    if "user_configs" not in tables:
        op.create_table(
            "user_configs",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("theme", sa.String(20), nullable=False, server_default="light"),
            sa.Column("language", sa.String(20), nullable=False, server_default="zh-CN"),
            sa.Column("default_page", sa.String(100), nullable=False, server_default="/"),
            sa.Column("embedding_model", sa.String(255), nullable=False, server_default="bge-small-zh-v1.5"),
            sa.Column("llm_model", sa.String(255), nullable=False, server_default="deepseek-chat"),
            sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
            sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default="1440"),
            sa.Column("two_factor_auth_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("ip_whitelist", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", name="uq_user_config_user"),
        )
        op.create_index("idx_user_config_user", "user_configs", ["user_id"])

    if "user_api_keys" not in tables:
        op.create_table(
            "user_api_keys",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("api_key_encrypted", sa.Text(), nullable=False),
            sa.Column("base_url", sa.String(500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("idx_user_api_key_user", "user_api_keys", ["user_id"])
        op.create_index("idx_user_api_key_provider", "user_api_keys", ["provider"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "user_api_keys" in tables:
        op.drop_index("idx_user_api_key_provider", table_name="user_api_keys")
        op.drop_index("idx_user_api_key_user", table_name="user_api_keys")
        op.drop_table("user_api_keys")
    if "user_configs" in tables:
        op.drop_index("idx_user_config_user", table_name="user_configs")
        op.drop_table("user_configs")
