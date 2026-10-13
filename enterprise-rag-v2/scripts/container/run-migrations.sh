#!/usr/bin/env bash
# =============================================================
# 数据库迁移启动脚本
#
# 逻辑：
#   1. 检查数据库完整性：alembic_version 表 + 关键 schema 表（users）
#   2. 若 schema 为空，删除 alembic_version 并重新初始化为起点
#   3. 执行 "alembic upgrade head" 运行所有待运行的迁移
#
# 所有迁移均做幂等处理，即使重复执行也安全。
# =============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "${APP_DIR}"

echo "[migrate] 开始数据库迁移检查..."

python3 - <<'PYEOF'
import os, sys
from sqlalchemy import create_engine, inspect, text

raw_url = os.environ.get("DATABASE_URL", "")
if not raw_url:
    print("[migrate] 未找到 DATABASE_URL，跳过迁移", flush=True)
    sys.exit(0)

sync_url = raw_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1) \
                  .replace("sqlite+aiosqlite", "sqlite", 1)

engine = create_engine(sync_url, pool_pre_ping=True)

try:
    inspector = inspect(engine)
    has_alembic_table = inspector.has_table("alembic_version")
    has_users_table = inspector.has_table("users")

    print("[migrate] 数据库状态检查:", flush=True)
    print(f"  - alembic_version 表: {'存在' if has_alembic_table else '不存在'}", flush=True)
    print(f"  - users 表: {'存在' if has_users_table else '不存在'}", flush=True)

    if has_alembic_table and not has_users_table:
        print("[migrate] 检测到 alembic_version 表存在但 schema 未创建，删除并重新初始化", flush=True)
        with engine.connect() as conn:
            try:
                conn.execute(text("DROP TABLE alembic_version"))
                conn.commit()
                print("[migrate] alembic_version 表已删除", flush=True)
            except Exception as e:
                print(f"[migrate] 删除失败（可能已删除）: {e}", flush=True)
                conn.commit()
    elif not has_alembic_table and not has_users_table:
        print("[migrate] 首次部署：将从第一个迁移开始运行", flush=True)
    elif has_alembic_table and has_users_table:
        print("[migrate] 检测到已有完整 schema，执行增量迁移", flush=True)

finally:
    engine.dispose()
PYEOF

echo "[migrate] 执行 alembic upgrade head..."
# 先升级到第一个迁移（创建 alembic_version 表），再扩宽列，再完成剩余迁移
python3 -m alembic upgrade 001_initial_schema 2>/dev/null || true

# 扩宽 alembic_version.version_num 至 128 字符（默认32，我们的迁移ID更长）
python3 - <<'PYEOF2'
import os
from sqlalchemy import create_engine, text

raw_url = os.environ.get("DATABASE_URL", "")
if not raw_url:
    import sys; sys.exit(0)
sync_url = raw_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1) \
                  .replace("sqlite+aiosqlite", "sqlite", 1)
engine = create_engine(sync_url, pool_pre_ping=True)
try:
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE IF EXISTS alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(128)"
        ))
        conn.commit()
    print("[migrate] alembic_version.version_num 已扩宽至 VARCHAR(128)", flush=True)
except Exception as e:
    print(f"[migrate] 扩宽列时出错（继续）: {e}", flush=True)
finally:
    engine.dispose()
PYEOF2

python3 -m alembic upgrade head

echo "[migrate] 数据库迁移完成 ✓"
