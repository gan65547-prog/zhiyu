"""Add workspace-scoped encrypted content connector credentials."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "040_add_content_connector_credentials"
down_revision: Union[str, None] = "039_align_dataset_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    u = postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)
    if "content_connector_credentials" not in tables:
        op.create_table(
            "content_connector_credentials",
            sa.Column("id", u, primary_key=True),
            sa.Column("tenant_id", u, nullable=False),
            sa.Column("workspace_id", u, nullable=False),
            sa.Column("platform", sa.String(64), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("encrypted_credentials", sa.Text(), nullable=False),
            sa.Column("credential_hint", sa.String(255), nullable=False, server_default="已配置"),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("created_by", u, nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("workspace_id", "platform", "name", name="uq_content_credential_workspace_platform_name"),
        )
        op.create_index("idx_content_credential_workspace", "content_connector_credentials", ["workspace_id", "platform", "status"])

    publish_columns = {column["name"] for column in inspector.get_columns("content_publish_records")}
    if "credential_id" not in publish_columns:
        op.add_column("content_publish_records", sa.Column("credential_id", u, nullable=True))
        if not is_sqlite:
            op.create_foreign_key("fk_publish_credential", "content_publish_records", "content_connector_credentials", ["credential_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    inspector = sa.inspect(bind)
    if "content_publish_records" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("content_publish_records")}
        if "credential_id" in columns:
            if not is_sqlite:
                op.drop_constraint("fk_publish_credential", "content_publish_records", type_="foreignkey")
            op.drop_column("content_publish_records", "credential_id")
    if "content_connector_credentials" in inspector.get_table_names():
        op.drop_index("idx_content_credential_workspace", table_name="content_connector_credentials")
        op.drop_table("content_connector_credentials")
