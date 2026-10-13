"""alembic_version.version_num 加长，兼容较长 revision id

Revision ID: 012_widen_alembic_version_num
Revises: 011_audit_logs_align_orm

包含：
- ALTER TABLE alembic_version 修改 version_num 列类型

添加了检查，确保只在必要时修改列类型，支持重复运行。
"""

from alembic import op
from sqlalchemy import inspect, String


revision = "012_widen_alembic_version_num"
down_revision = "011_fix_opsquotadimension_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查 alembic_version 表中 version_num 列的当前类型
    bind = op.get_bind()
    # SQLite stores VARCHAR length metadata but does not support PostgreSQL's
    # ALTER COLUMN TYPE syntax. Its text column is already unbounded for this
    # bookkeeping value, so no rewrite is required.
    if bind.dialect.name == "sqlite":
        return
    inspector = inspect(bind)

    # 获取 alembic_version 表的列信息
    columns = inspector.get_columns('alembic_version')
    version_num_col = next((col for col in columns if col['name'] == 'version_num'), None)

    if version_num_col:
        # 检查当前列类型长度是否小于 128
        # VARCHAR 类型的长度存储在 column.type.length 中
        current_type = version_num_col.get('type')
        current_length = getattr(current_type, 'length', 32)

        # 如果当前长度小于 128，则执行 ALTER
        if current_length is None or current_length < 128:
            op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")


def downgrade() -> None:
    # 008a is the only safe point to shrink this column. Keeping it wide here
    # is required because later downgrade steps still write long revision ids.
    return
