from app.db_connection import OpsConn


class _Capture:
    def __init__(self) -> None:
        self.last_sql: str | None = None
        self.last_params: tuple = ()

    def execute(self, sql: str, params=None):
        self.last_sql = sql
        self.last_params = params or ()

        class _R:
            def fetchall(self_inner):
                return []

        return _R()


def test_opsconn_adapts_placeholders_for_postgresql():
    cap = _Capture()
    conn = OpsConn(cap, "postgresql")
    conn.fetchall("SELECT a FROM t WHERE x = ? AND y = datetime('now')", (1,))
    assert "?" not in cap.last_sql
    assert "%s" in cap.last_sql
    assert "CURRENT_TIMESTAMP" in cap.last_sql
    assert cap.last_params == (1,)


def test_opsconn_sqlite_leaves_sql_unchanged():
    cap = _Capture()
    conn = OpsConn(cap, "sqlite")
    conn.fetchall("SELECT ? FROM t", (2,))
    assert "?" in cap.last_sql
