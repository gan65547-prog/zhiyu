"""
Alembic环境配置

配置数据库迁移环境
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 导入模型
from infrastructure.database.models import Base
from core.config import get_settings


# 本版本的迁移门禁只负责 AI 工作台及其直接依赖的业务表。
# 仓库还包含制造、学习和旧版运营中心模型，它们有独立的生命周期，
# 既没有纳入本版本迁移链，也不应在工作台发布时被 autogenerate 误删/误建。
WORKBENCH_SCHEMA_TABLES = {
    "tenants", "users", "workspaces", "workspace_members", "datasets",
    "documents", "document_chunks", "conversations", "messages",
    "assets", "document_copy_status", "document_annotations", "document_errata",
    "knowledge_items", "knowledge_evidence", "knowledge_item_versions", "knowledge_relations",
    "research_projects", "research_questions", "research_samples", "research_runs",
    "research_sources", "research_evidence", "research_findings", "research_reports",
    "agent_definitions", "agent_runs", "agent_run_steps", "agent_outputs",
    "agent_approvals", "agent_schedules",
    "content_topics", "content_drafts", "content_publish_records",
    "content_connector_credentials", "content_metrics", "content_metric_sync_runs",
    "content_retrospectives", "audit_logs", "user_configs", "user_api_keys",
}
LEGACY_COLUMNS = {("audit_logs", "request_id")}


def include_workbench_object(object_, name, type_, reflected, compare_to):
    """将 Alembic autogenerate 限定在当前版本实际交付的 schema 边界内。"""
    if type_ == "table":
        return name in WORKBENCH_SCHEMA_TABLES
    # 现有迁移链已固定外键的业务语义；不同历史迁移在 PostgreSQL 上的
    # constraint name/ondelete 表达不同，不应由本版本 autogenerate 重写。
    if type_ == "foreign_key_constraint":
        return False
    if type_ in {"index", "unique_constraint", "primary_key_constraint", "check_constraint"}:
        return False
    # 历史迁移已固定现有列的 nullable/comment；保留新增/删除列检测，
    # 避免仅因旧迁移未记录的表达差异阻塞当前版本。
    if type_ == "column" and compare_to is not None:
        return False
    if type_ == "column" and (getattr(getattr(object_, "table", None), "name", None), name) in LEGACY_COLUMNS:
        return False

    table = getattr(object_, "table", None)
    table_name = getattr(table, "name", None)
    if table_name is not None:
        return table_name in WORKBENCH_SCHEMA_TABLES
    return True

# Alembic Config对象
config = context.config

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata

# 从环境变量获取数据库URL
settings = get_settings()
# Alembic 在线迁移使用同步 Engine：asyncpg URL 会触发 MissingGreenlet，需换同步驱动
db_url = settings.database.url
if db_url.startswith("sqlite+aiosqlite"):
    db_url = db_url.replace("sqlite+aiosqlite", "sqlite")
elif db_url.startswith("postgresql+asyncpg"):
    db_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """
    离线模式运行迁移
    
    在离线模式下，不需要实际的数据库连接，
    只生成SQL脚本
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式运行迁移
    
    在在线模式下，创建Engine并关联连接
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_workbench_object,
            compare_type=False,
            compare_server_default=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
