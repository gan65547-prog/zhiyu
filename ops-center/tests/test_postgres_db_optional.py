"""
可选：在设置 OPS_TEST_DATABASE_URL 时验证 PostgreSQL 建表与 OpsConn。

本地示例：
  docker run -d --name pg-ops -e POSTGRES_PASSWORD=ops -e POSTGRES_USER=ops -e POSTGRES_DB=ops_center -p 5434:5432 postgres:16-alpine
  export OPS_TEST_DATABASE_URL=postgresql://ops:ops@127.0.0.1:5434/ops_center
  RUN_POSTGRES_OPS_TEST=1 pytest ops-center/tests/test_postgres_db_optional.py -q
"""

import os

import pytest


@pytest.mark.skipif(
    not os.getenv("RUN_POSTGRES_OPS_TEST"),
    reason="set RUN_POSTGRES_OPS_TEST=1 and OPS_TEST_DATABASE_URL to run",
)
def test_init_db_postgres_smoke():
    from app.config import get_settings

    url = os.getenv("OPS_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("OPS_TEST_DATABASE_URL not set")

    os.environ["OPS_DATABASE_URL"] = url
    get_settings.cache_clear()

    from app.db import init_db
    from app.auth.user_store import init_user_store

    conn = init_db()
    try:
        assert conn.dialect == "postgresql"
        init_user_store(conn)
        rows = conn.fetchall("SELECT code FROM ops_roles ORDER BY code")
        codes = {r["code"] for r in rows}
        assert "super_admin" in codes
    finally:
        conn.close()
        os.environ.pop("OPS_DATABASE_URL", None)
        get_settings.cache_clear()
