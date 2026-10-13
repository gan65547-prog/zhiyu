from __future__ import annotations

from typing import Any, Literal


class OpsConn:
    """统一 sqlite3 / psycopg 的占位符与日期函数，供运维用户仓储使用。"""

    def __init__(self, raw: Any, dialect: Literal["sqlite", "postgresql"]) -> None:
        self._raw = raw
        self.dialect = dialect

    def _adapt(self, sql: str) -> str:
        if self.dialect != "postgresql":
            return sql
        s = sql.replace("datetime('now')", "CURRENT_TIMESTAMP")
        return s.replace("?", "%s")

    def execute(self, sql: str, params: tuple = ()) -> Any:
        sql = self._adapt(sql)
        p = params or ()
        if self.dialect == "sqlite":
            return self._raw.execute(sql, p)
        return self._raw.execute(sql, p)

    def fetchall(self, sql: str, params: tuple = ()) -> list[Any]:
        sql = self._adapt(sql)
        p = params or ()
        if self.dialect == "sqlite":
            return self._raw.execute(sql, p).fetchall()
        res = self._raw.execute(sql, p)
        return list(res.fetchall())

    def commit(self) -> None:
        self._raw.commit()

    def close(self) -> None:
        self._raw.close()
