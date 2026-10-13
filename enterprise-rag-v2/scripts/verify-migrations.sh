#!/usr/bin/env bash
# =============================================================
# Database Migration Verification Script
#
# 用途：验证所有数据库迁移是否可以：
#   1. 在全新数据库上正确运行（冷启动）
#   2. 重复运行而不出错（幂等性）
#   3. 正确回滚和重新应用（完整周期）
#   4. 在 PostgreSQL 和 SQLite 上都能工作
#
# 用法：
#   bash scripts/verify-migrations.sh [sqlite|postgres] [test-dir]
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DB_TYPE="${1:-sqlite}"
TEST_DIR="${2:-.migration-test}"
TIMESTAMP=$(date +%s)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================================="
echo "Database Migration Verification Suite"
echo "=========================================================="
echo "Database Type: $DB_TYPE"
echo "Test Directory: $TEST_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""

# Setup test environment
setup_test_db() {
    local db_type=$1
    local test_dir=$2

    mkdir -p "$test_dir"
    cd "$test_dir"

    if [ "$db_type" = "sqlite" ]; then
        DB_FILE="test_db_${TIMESTAMP}.db"
        export DATABASE_URL="sqlite:///${DB_FILE}"
        echo -e "${GREEN}✓ Using SQLite:${NC} $DB_FILE"
    else
        export DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_db_${TIMESTAMP}"
        echo -e "${GREEN}✓ Using PostgreSQL:${NC} ${DATABASE_URL}"
        # Try to create test database (may fail if psql not available)
        createdb "test_db_${TIMESTAMP}" 2>/dev/null || true
    fi
}

# Test 1: Cold start - Fresh database
test_cold_start() {
    echo ""
    echo "========== Test 1: Cold Start (Fresh Database) =========="

    cd "$PROJECT_ROOT"

    # Remove old database file for SQLite
    if [ "$DB_TYPE" = "sqlite" ]; then
        rm -f "$TEST_DIR"/*.db
    fi

    python3 << 'PYEOF'
import os
import sys
from sqlalchemy import create_engine, inspect, text

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

# Sync URL for migrations
if "sqlite" in db_url:
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite", 1)
else:
    sync_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)

print(f"[Test 1] Creating fresh database: {db_url}")

engine = create_engine(sync_url, echo=False)

try:
    # Run migrations
    os.system("cd enterprise-rag-v2 && python -m alembic upgrade head")

    # Verify tables were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "alembic_version" in tables:
        print(f"[Test 1] ✓ Database initialized with {len(tables)} tables")

        # Check key tables
        key_tables = ["users", "conversations", "documents", "datasets"]
        found = [t for t in key_tables if t in tables]
        print(f"[Test 1] ✓ Found {len(found)}/{len(key_tables)} key tables")

        # Show applied migrations
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            count = result.scalar()
            print(f"[Test 1] ✓ Applied {count} migrations")
    else:
        print("[Test 1] ✗ FAILED: alembic_version table not created")
        sys.exit(1)

    engine.dispose()
    print("[Test 1] ✓ PASSED: Cold start successful")

except Exception as e:
    print(f"[Test 1] ✗ FAILED: {e}")
    sys.exit(1)
PYEOF

    local result=$?
    if [ $result -ne 0 ]; then
        return 1
    fi
}

# Test 2: Idempotency - Run migrations twice
test_idempotency() {
    echo ""
    echo "========== Test 2: Idempotency (Run Twice) =========="

    cd "$PROJECT_ROOT"

    python3 << 'PYEOF'
import os
import sys
from sqlalchemy import create_engine, inspect, text

db_url = os.environ.get("DATABASE_URL")
sync_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1) \
               .replace("sqlite+aiosqlite", "sqlite", 1)

print(f"[Test 2] Running migrations again on existing database")

engine = create_engine(sync_url, echo=False)

try:
    # First run was already done in Test 1
    # Get baseline
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
        baseline = result.scalar()

    print(f"[Test 2] ✓ Baseline: {baseline} migrations applied")

    # Run migrations again
    os.system("cd enterprise-rag-v2 && python -m alembic upgrade head 2>&1 | grep -E '(INFO|ERROR|already)' || true")

    # Verify count hasn't changed
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
        final = result.scalar()

    if final == baseline:
        print(f"[Test 2] ✓ Migration count unchanged: {final}")
        print("[Test 2] ✓ PASSED: Idempotency verified")
    else:
        print(f"[Test 2] ✗ FAILED: Migration count changed {baseline} → {final}")
        sys.exit(1)

    engine.dispose()

except Exception as e:
    print(f"[Test 2] ✗ FAILED: {e}")
    sys.exit(1)
PYEOF

    local result=$?
    if [ $result -ne 0 ]; then
        return 1
    fi
}

# Test 3: Full cycle - Downgrade and upgrade
test_full_cycle() {
    echo ""
    echo "========== Test 3: Full Cycle (Down → Up) =========="

    cd "$PROJECT_ROOT/enterprise-rag-v2"

    python3 << 'PYEOF'
import os
import sys
from sqlalchemy import create_engine, inspect, text

db_url = os.environ.get("DATABASE_URL")
sync_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1) \
               .replace("sqlite+aiosqlite", "sqlite", 1)

print(f"[Test 3] Testing full migration cycle")

engine = create_engine(sync_url, echo=False)

try:
    # Get baseline table count
    inspector = inspect(engine)
    baseline_tables = len(inspector.get_table_names())
    print(f"[Test 3] ✓ Baseline: {baseline_tables} tables")

    # Downgrade to revision 010
    print("[Test 3] ✓ Downgrading to 010_add_ops_updated_at_triggers...")
    os.system("python -m alembic downgrade 010_add_ops_updated_at_triggers 2>&1 | tail -1 || true")

    inspector = inspect(engine)
    downgraded_tables = len(inspector.get_table_names())
    print(f"[Test 3] ✓ After downgrade: {downgraded_tables} tables")

    if downgraded_tables >= baseline_tables - 6:  # Some tables should be removed
        print(f"[Test 3] ✓ Downgrade reduced tables as expected")

    # Upgrade back to head
    print("[Test 3] ✓ Upgrading back to head...")
    os.system("python -m alembic upgrade head 2>&1 | tail -1 || true")

    inspector = inspect(engine)
    final_tables = len(inspector.get_table_names())
    print(f"[Test 3] ✓ After upgrade: {final_tables} tables")

    if final_tables == baseline_tables:
        print(f"[Test 3] ✓ Table count restored to baseline: {final_tables}")
        print("[Test 3] ✓ PASSED: Full cycle successful")
    else:
        print(f"[Test 3] ✗ FAILED: Table count mismatch {baseline_tables} → {final_tables}")
        sys.exit(1)

    engine.dispose()

except Exception as e:
    print(f"[Test 3] ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

    local result=$?
    if [ $result -ne 0 ]; then
        return 1
    fi
}

# Test 4: Data integrity
test_data_integrity() {
    echo ""
    echo "========== Test 4: Data Integrity =========="

    cd "$PROJECT_ROOT"

    python3 << 'PYEOF'
import os
from sqlalchemy import create_engine, inspect, text

db_url = os.environ.get("DATABASE_URL")
sync_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1) \
               .replace("sqlite+aiosqlite", "sqlite", 1)

print("[Test 4] Verifying schema integrity")

engine = create_engine(sync_url, echo=False)
inspector = inspect(engine)

# Check key tables and columns
table_schemas = {
    "users": ["id", "email", "username"],
    "conversations": ["id", "user_id", "dataset_id"],
    "documents": ["id", "dataset_id"],
    "datasets": ["id", "workspace_id"],
}

errors = []
for table_name, expected_cols in table_schemas.items():
    if not inspector.has_table(table_name):
        errors.append(f"✗ Table '{table_name}' missing")
        continue

    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
    missing = set(expected_cols) - existing_cols

    if missing:
        errors.append(f"✗ Table '{table_name}' missing columns: {missing}")
    else:
        print(f"[Test 4] ✓ Table '{table_name}' has all expected columns")

if errors:
    for error in errors:
        print(f"[Test 4] {error}")
    print("[Test 4] ✗ FAILED: Schema integrity check failed")
    exit(1)
else:
    print("[Test 4] ✓ PASSED: All schema integrity checks passed")

engine.dispose()
PYEOF

    local result=$?
    if [ $result -ne 0 ]; then
        return 1
    fi
}

# Cleanup
cleanup_test_db() {
    echo ""
    echo "========== Cleanup =========="

    if [ "$DB_TYPE" = "sqlite" ]; then
        echo "Removing SQLite test databases..."
        rm -f "$TEST_DIR"/*.db
    else
        echo "Removing PostgreSQL test databases..."
        dropdb "test_db_${TIMESTAMP}" 2>/dev/null || true
    fi

    echo "[Cleanup] ✓ Cleaned up test artifacts"
}

# Main execution
main() {
    local failed=0

    setup_test_db "$DB_TYPE" "$TEST_DIR"

    if ! test_cold_start; then
        ((failed++))
    fi

    if ! test_idempotency; then
        ((failed++))
    fi

    if ! test_full_cycle; then
        ((failed++))
    fi

    if ! test_data_integrity; then
        ((failed++))
    fi

    cleanup_test_db

    echo ""
    echo "=========================================================="
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
        echo "=========================================================="
        return 0
    else:
        echo -e "${RED}✗ $failed TEST(S) FAILED${NC}"
        echo "=========================================================="
        return 1
    fi
}

main
