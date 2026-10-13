from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.db_connection import OpsConn

_DEFAULT_ROLES: list[tuple[str, str, str]] = [
    ("super_admin", "超级管理员", "平台级全权限"),
    ("tenant_ops", "租户运维", "租户与配额运维"),
    ("read_only_auditor", "审计只读", "仅查看审计与报表"),
]


def _connect_sqlite(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _table_list(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r["name"] for r in rows}


def _seed_roles_sqlite(conn: sqlite3.Connection) -> None:
    for code, name, description in _DEFAULT_ROLES:
        conn.execute(
            """
            INSERT OR IGNORE INTO ops_roles (id, code, name, description)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid4()), code, name, description),
        )
    conn.commit()


def _seed_roles_postgres(conn) -> None:
    for code, name, description in _DEFAULT_ROLES:
        conn.execute(
            """
            INSERT INTO ops_roles (id, code, name, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING
            """,
            (str(uuid4()), code, name, description),
        )
    conn.commit()


def _migrate_legacy_roles_json(conn: sqlite3.Connection) -> None:
    if "ops_users" not in _table_list(conn):
        return
    cols = _table_columns(conn, "ops_users")
    if "roles_json" not in cols:
        return
    valid_codes = {r["code"] for r in conn.execute("SELECT code FROM ops_roles").fetchall()}
    rows = conn.execute("SELECT id, roles_json FROM ops_users").fetchall()
    for row in rows:
        try:
            roles = json.loads(row["roles_json"] or "[]")
        except (json.JSONDecodeError, TypeError):
            roles = []
        for role_code in roles:
            if not role_code:
                continue
            if str(role_code) not in valid_codes:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO ops_user_roles (id, ops_user_id, role_code, created_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (str(uuid4()), row["id"], str(role_code)),
            )
    conn.commit()
    try:
        conn.execute("ALTER TABLE ops_users DROP COLUMN roles_json")
        conn.commit()
    except sqlite3.OperationalError:
        pass


def _init_schema_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_roles (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_user_roles (
            id TEXT PRIMARY KEY,
            ops_user_id TEXT NOT NULL,
            role_code TEXT NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (ops_user_id, role_code),
            FOREIGN KEY (ops_user_id) REFERENCES ops_users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_code) REFERENCES ops_roles(code) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_user_roles_user ON ops_user_roles (ops_user_id)")
    conn.commit()

    _seed_roles_sqlite(conn)

    if "roles_json" in _table_columns(conn, "ops_users"):
        _migrate_legacy_roles_json(conn)

    conn.commit()


def _init_schema_postgres(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_roles (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active SMALLINT NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_user_roles (
            id TEXT PRIMARY KEY,
            ops_user_id TEXT NOT NULL REFERENCES ops_users(id) ON DELETE CASCADE,
            role_code TEXT NOT NULL REFERENCES ops_roles(code) ON DELETE CASCADE,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (ops_user_id, role_code)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ops_user_roles_user ON ops_user_roles (ops_user_id)"
    )
    conn.commit()
    _seed_roles_postgres(conn)


def init_db() -> OpsConn:
    settings = get_settings()
    if settings.ops_database_url and settings.ops_database_url.strip():
        import psycopg
        from psycopg.rows import dict_row

        raw = psycopg.connect(settings.ops_database_url, row_factory=dict_row)
        _init_schema_postgres(raw)
        return OpsConn(raw, "postgresql")

    db_path = Path(settings.ops_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    raw = _connect_sqlite(str(db_path))
    _init_schema_sqlite(raw)
    return OpsConn(raw, "sqlite")
