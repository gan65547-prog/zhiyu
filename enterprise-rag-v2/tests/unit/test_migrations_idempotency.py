"""
Database Migration Idempotency Tests

验证所有数据库迁移可以安全地重复运行而不出错。
使用 pytest 框架运行。

运行方式：
    pytest tests/unit/test_migrations_idempotency.py -v
"""
import os
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def test_db_engine():
    """Create an in-memory SQLite database for testing"""
    # Use in-memory SQLite for fast tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def setup_env():
    """Set up test environment variables"""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    yield
    # Cleanup
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


class TestMigrationIdempotency:
    """Test that all migrations are idempotent and can be run multiple times"""

    def test_sqlite_full_chain_upgrade_idempotency_and_downgrade(self, tmp_path, monkeypatch):
        """The supported local SQLite path must exercise a real file, not a detached in-memory engine."""
        from alembic.command import downgrade, upgrade
        from alembic.config import Config

        database_url = f"sqlite:///{tmp_path / 'migration-regression.db'}"
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'migration-regression.db'}")
        from core.config import get_settings
        get_settings.cache_clear()
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", database_url)

        try:
            upgrade(config, "head")
            engine = create_engine(database_url)
            inspector = inspect(engine)
            assert inspector.has_table("alembic_version")
            assert inspector.has_table("users")
            assert inspector.has_table("agent_runs")
            engine.dispose()

            # A second head run must be a no-op, not a second table/index creation.
            upgrade(config, "head")
            engine = create_engine(database_url)
            assert inspect(engine).has_table("agent_schedules")
            engine.dispose()

            downgrade(config, "base")
            engine = create_engine(database_url)
            assert not inspect(engine).has_table("users")
            engine.dispose()
        finally:
            get_settings.cache_clear()

    @pytest.mark.xfail(reason="需要 PostgreSQL（migrations 010/012 包含 PostgreSQL 专用 SQL）", strict=False)
    def test_all_migrations_apply_cleanly(self, test_db_engine):
        """Test 1: Verify all migrations apply without errors on fresh database"""
        from alembic.config import Config
        from alembic.command import upgrade

        # Get alembic config
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        # Apply all migrations
        try:
            upgrade(config, "head")
        except Exception as e:
            pytest.fail(f"Failed to apply migrations: {e}")

        # Verify alembic_version table exists
        inspector = inspect(test_db_engine)
        assert inspector.has_table("alembic_version"), "alembic_version table not created"

        # Get count of applied migrations
        with test_db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            migration_count = result.scalar()

        assert migration_count > 0, f"No migrations applied: {migration_count}"

    @pytest.mark.xfail(reason="需要 PostgreSQL（migrations 010/012 包含 PostgreSQL 专用 SQL）", strict=False)
    def test_migrations_idempotent_on_rerun(self, test_db_engine):
        """Test 2: Verify migrations don't fail when run twice"""
        from alembic.config import Config
        from alembic.command import upgrade

        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        # First run
        upgrade(config, "head")

        # Get baseline
        with test_db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            baseline_count = result.scalar()
            result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            baseline_tables = result.scalar()

        # Second run - should be a no-op and not fail
        try:
            upgrade(config, "head")
        except Exception as e:
            pytest.fail(f"Failed on second migration run: {e}")

        # Verify counts haven't changed
        with test_db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            final_count = result.scalar()
            result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            final_tables = result.scalar()

        assert final_count == baseline_count, (
            f"Migration count changed on rerun: {baseline_count} → {final_count}"
        )
        assert final_tables == baseline_tables, (
            f"Table count changed on rerun: {baseline_tables} → {final_tables}"
        )

    @pytest.mark.xfail(reason="项目 alembic/ 目录遮蔽 site-packages alembic 包", strict=False)
    def test_migration_chain_is_linear(self, test_db_engine):
        """Test 3: Verify migration chain has no branches"""
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)

        # Check migration chain
        revisions = {}
        for migration in script.walk_revisions():
            if migration.revision:
                # Parse down_revision
                if isinstance(migration.down_revision, (list, tuple)):
                    # Merge migration - should only be 013
                    if migration.revision != "013_merge_branches":
                        pytest.fail(
                            f"Unexpected merge migration found: {migration.revision} "
                            f"(down_revision: {migration.down_revision})"
                        )
                    assert len(migration.down_revision) == 1, (
                        f"Merge migration {migration.revision} has multiple parents"
                    )
                revisions[migration.revision] = migration.down_revision

        assert len(revisions) > 0, "No migrations found"

        # Verify no branching points (except 013)
        down_rev_usage = {}
        for rev, down in revisions.items():
            if isinstance(down, (list, tuple)):
                down = down[0] if down else None

            if down:
                if down not in down_rev_usage:
                    down_rev_usage[down] = []
                down_rev_usage[down].append(rev)

        for rev, followers in down_rev_usage.items():
            if len(followers) > 1:
                if rev != "010_add_ops_updated_at_triggers":
                    pytest.fail(
                        f"Branching point found at {rev}: {followers}. "
                        f"Expected linear chain."
                    )

    @pytest.mark.xfail(reason="需要 PostgreSQL（migrations 010/012 包含 PostgreSQL 专用 SQL）", strict=False)
    def test_key_tables_created(self, test_db_engine):
        """Test 4: Verify all expected tables are created"""
        from alembic.config import Config
        from alembic.command import upgrade

        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        upgrade(config, "head")

        inspector = inspect(test_db_engine)
        tables = inspector.get_table_names()

        # Check for key tables
        expected_tables = [
            "users",
            "conversations",
            "documents",
            "datasets",
            "workspaces",
            "audit_logs",
        ]

        for table in expected_tables:
            assert table in tables, f"Expected table '{table}' not found in database"

    @pytest.mark.xfail(reason="需要 PostgreSQL（migrations 010/012 包含 PostgreSQL 专用 SQL）", strict=False)
    def test_key_columns_exist(self, test_db_engine):
        """Test 5: Verify key columns exist in critical tables"""
        from alembic.config import Config
        from alembic.command import upgrade

        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        upgrade(config, "head")

        inspector = inspect(test_db_engine)

        # Check critical columns
        checks = {
            "conversations": ["id", "user_id", "dataset_id", "visibility", "workspace_id"],
            "documents": ["id", "dataset_id"],
            "datasets": ["id", "workspace_id"],
            "audit_logs": [
                "id",
                "action",
                "resource_type",
                "user_id",
                "resource_id",
                "error_message",
            ],
        }

        for table, expected_cols in checks.items():
            if not inspector.has_table(table):
                continue

            existing_cols = {c["name"] for c in inspector.get_columns(table)}

            for col in expected_cols:
                assert col in existing_cols, (
                    f"Column '{col}' missing in table '{table}'. "
                    f"Existing columns: {existing_cols}"
                )

    @pytest.mark.xfail(reason="需要 PostgreSQL（migrations 010/012 包含 PostgreSQL 专用 SQL）", strict=False)
    def test_foreign_key_constraints(self, test_db_engine):
        """Test 6: Verify foreign key relationships are intact"""
        from alembic.config import Config
        from alembic.command import upgrade

        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        upgrade(config, "head")

        inspector = inspect(test_db_engine)

        # SQLite may not enforce foreign keys by default, but we can check schema
        # Check that foreign key relationships are defined in schema

        if inspector.has_table("conversations"):
            fks = inspector.get_foreign_keys("conversations")
            fk_names = [fk["name"] for fk in fks]

            # Should have foreign key to users table
            assert any("user" in name.lower() for name in fk_names), (
                "Missing user foreign key in conversations table"
            )

    @pytest.mark.xfail(reason="需要 PostgreSQL（migrations 010/012 包含 PostgreSQL 专用 SQL）", strict=False)
    def test_indexes_created(self, test_db_engine):
        """Test 7: Verify performance indexes are created"""
        from alembic.config import Config
        from alembic.command import upgrade

        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        upgrade(config, "head")

        inspector = inspect(test_db_engine)

        # Check for key indexes
        if inspector.has_table("conversations"):
            indexes = inspector.get_indexes("conversations")
            index_names = {idx["name"] for idx in indexes}

            assert any("user" in name for name in index_names), (
                "Missing user-related index in conversations table"
            )


class TestMigrationContent:
    """Test the correctness of individual migrations"""

    def test_migration_files_exist(self):
        """Test 8: Verify all migration files exist"""
        import glob

        migration_dir = "alembic/versions"
        migrations = glob.glob(f"{migration_dir}/*.py")

        # Should have at least 16 migrations (001-016)
        assert len(migrations) >= 16, (
            f"Expected at least 16 migration files, found {len(migrations)}"
        )

    def test_migrations_have_idempotency_patterns(self):
        """Test 9: Verify migrations use idempotency patterns"""
        import os
        import re

        migration_dir = "alembic/versions"
        idempotency_patterns = [
            r"inspect\(bind\)",
            r"existing_tables",
            r"IF NOT EXISTS",
            r"DROP IF EXISTS",
            r"\.get_columns\(",
            r"\.has_table\(",
        ]

        # Migrations that should have idempotency checks
        critical_migrations = [
            "003_add_user_id_to_conversations.py",
            "004_mvp_commercialization.py",
            "005_add_integration_tables.py",
            "006_add_conversation_permissions.py",
            "007_add_platform_app_configs.py",
            "008_add_ops_center_tables.py",
            "010_add_ops_updated_at_triggers.py",
            "012_widen_alembic_version_num.py",
        ]

        for migration_file in critical_migrations:
            path = os.path.join(migration_dir, migration_file)
            if not os.path.exists(path):
                continue

            with open(path, "r") as f:
                content = f.read()

            if migration_file == "004_mvp_commercialization.py":
                assert "audit_logs" in content
                assert all(term not in content for term in ("subscriptions", "payments", "redeem"))
                continue

            has_pattern = any(re.search(pattern, content) for pattern in idempotency_patterns)

            assert has_pattern, (
                f"Migration '{migration_file}' lacks idempotency patterns. "
                f"Expected at least one of: {idempotency_patterns}"
            )

    def test_migration_chain_connectivity(self):
        """Test 10: Verify migration chain is properly connected"""
        import os
        import re

        migration_dir = "alembic/versions"

        # Read all migrations
        migrations = {}
        for file in os.listdir(migration_dir):
            if not file.endswith(".py") or file.startswith("__"):
                continue

            path = os.path.join(migration_dir, file)
            with open(path, "r") as f:
                content = f.read()

            # Extract revision
            rev_match = re.search(
                r'revision\s*(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', content
            )
            # Extract down_revision (支持带 type annotation 和不带两种写法)
            down_match = re.search(r"down_revision(?:\s*:\s*[^=]+)?\s*=\s*(.+?)$", content, re.MULTILINE)

            if rev_match:
                rev = rev_match.group(1)
                down = down_match.group(1).strip() if down_match else "None"
                migrations[rev] = down

        # Verify chain starts at 001
        assert "001_initial_schema" in migrations, "Missing 001_initial_schema"

        # Verify chain is connected (each migration links to a previous one)
        for rev, down in migrations.items():
            if down == "None":
                assert rev == "001_initial_schema", (
                    f"Only 001_initial_schema should have down_revision=None, "
                    f"but {rev} also does"
                )
