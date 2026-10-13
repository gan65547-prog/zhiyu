from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from app.auth.password_hashing import hash_password, verify_password
from app.config import get_settings

if TYPE_CHECKING:
    from app.db_connection import OpsConn


@dataclass
class OpsUser:
    id: str
    username: str
    password_hash: str
    is_active: bool
    roles: list[str]


_FALLBACK_ROLES: list[dict[str, str | None]] = [
    {"code": "super_admin", "name": "超级管理员", "description": "平台级全权限"},
    {"code": "tenant_ops", "name": "租户运维", "description": "租户与配额运维"},
    {"code": "read_only_auditor", "name": "审计只读", "description": "仅查看审计与报表"},
]


class SqliteOpsUserStore:
    """ops_users + ops_roles + ops_user_roles（SQLite 或 PostgreSQL）。"""

    def __init__(self, conn: Optional["OpsConn"] = None) -> None:
        self._conn = conn
        settings = get_settings()
        self._users: dict[str, OpsUser] = {}
        if self._conn:
            self._load_users_from_db()
        if settings.bootstrap_admin_username not in self._users:
            admin_roles = sorted(
                {r.strip() for r in settings.bootstrap_admin_roles.split(",") if r.strip()}
            )
            admin = OpsUser(
                id=str(uuid4()),
                username=settings.bootstrap_admin_username,
                password_hash=hash_password(settings.bootstrap_admin_password),
                is_active=True,
                roles=admin_roles,
            )
            self._users[admin.username] = admin
            if self._conn:
                self._insert_user_row(admin)
                self._replace_roles(admin.id, admin.roles)

    def _valid_role_codes(self) -> set[str]:
        if not self._conn:
            return {"super_admin", "tenant_ops", "read_only_auditor"}
        rows = self._conn.fetchall("SELECT code FROM ops_roles")
        return {r["code"] for r in rows}

    def _load_users_from_db(self) -> None:
        assert self._conn is not None
        user_rows = self._conn.fetchall(
            "SELECT id, username, password_hash, is_active FROM ops_users ORDER BY username"
        )
        role_rows = self._conn.fetchall(
            """
            SELECT ur.ops_user_id, ur.role_code
            FROM ops_user_roles ur
            ORDER BY ur.ops_user_id, ur.role_code
            """
        )
        roles_by_uid: dict[str, list[str]] = {}
        for r in role_rows:
            roles_by_uid.setdefault(r["ops_user_id"], []).append(r["role_code"])
        for row in user_rows:
            uid = row["id"]
            self._users[row["username"]] = OpsUser(
                id=uid,
                username=row["username"],
                password_hash=row["password_hash"],
                is_active=bool(row["is_active"]),
                roles=roles_by_uid.get(uid, []),
            )

    def _insert_user_row(self, user: OpsUser) -> None:
        if not self._conn:
            return
        self._conn.execute(
            """
            INSERT INTO ops_users (id, username, password_hash, is_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash=excluded.password_hash,
                is_active=excluded.is_active,
                updated_at=datetime('now')
            """,
            (user.id, user.username, user.password_hash, int(user.is_active)),
        )
        self._conn.commit()

    def _update_user_row(self, user: OpsUser) -> None:
        if not self._conn:
            return
        self._conn.execute(
            """
            UPDATE ops_users
            SET password_hash = ?, is_active = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (user.password_hash, int(user.is_active), user.id),
        )
        self._conn.commit()

    def _replace_roles(self, ops_user_id: str, roles: list[str]) -> None:
        if not self._conn:
            return
        roles = sorted(set(roles))
        valid = self._valid_role_codes()
        for code in roles:
            if code not in valid:
                raise ValueError(f"INVALID_ROLE:{code}")
        self._conn.execute("DELETE FROM ops_user_roles WHERE ops_user_id = ?", (ops_user_id,))
        for code in roles:
            self._conn.execute(
                """
                INSERT INTO ops_user_roles (id, ops_user_id, role_code, created_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (str(uuid4()), ops_user_id, code),
            )
        self._conn.commit()

    def authenticate(self, username: str, password: str) -> OpsUser | None:
        user = self._users.get(username)
        if not user or not user.is_active:
            return None
        ok, new_hash = verify_password(password, user.password_hash)
        if not ok:
            return None
        if new_hash:
            user.password_hash = new_hash
            if self._conn:
                self._update_user_row(user)
        return user

    def get_user(self, username: str) -> OpsUser | None:
        return self._users.get(username)

    def list_users(self) -> list[OpsUser]:
        return sorted(self._users.values(), key=lambda x: x.username)

    def list_roles(self) -> list[dict[str, str | None]]:
        if not self._conn:
            return list(_FALLBACK_ROLES)
        rows = self._conn.fetchall("SELECT code, name, description FROM ops_roles ORDER BY code")
        return [
            {"code": r["code"], "name": r["name"], "description": r["description"]}
            for r in rows
        ]

    def create_user(self, username: str, password: str, roles: list[str] | None = None) -> OpsUser:
        if username in self._users:
            raise ValueError("USER_ALREADY_EXISTS")
        role_list = sorted(set(roles or ["read_only_auditor"]))
        user = OpsUser(
            id=str(uuid4()),
            username=username,
            password_hash=hash_password(password),
            is_active=True,
            roles=role_list,
        )
        self._users[username] = user
        if self._conn:
            try:
                self._insert_user_row(user)
                self._replace_roles(user.id, role_list)
            except Exception:
                del self._users[username]
                raise
        return user

    def update_user(
        self,
        username: str,
        *,
        password: str | None = None,
        is_active: bool | None = None,
    ) -> OpsUser:
        user = self._users.get(username)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        if password is not None:
            user.password_hash = hash_password(password)
        if is_active is not None:
            user.is_active = is_active
        if self._conn:
            self._update_user_row(user)
        return user

    def delete_user(self, username: str) -> None:
        if username not in self._users:
            raise ValueError("USER_NOT_FOUND")
        user = self._users.pop(username)
        if self._conn:
            self._conn.execute("DELETE FROM ops_users WHERE id = ?", (user.id,))
            self._conn.commit()

    def assign_roles(self, username: str, roles: list[str]) -> OpsUser:
        user = self._users.get(username)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        self._replace_roles(user.id, roles)
        user.roles = sorted(set(roles))
        return user


USER_STORE = SqliteOpsUserStore()


def init_user_store(conn: Optional["OpsConn"]) -> SqliteOpsUserStore:
    global USER_STORE
    USER_STORE = SqliteOpsUserStore(conn=conn)
    return USER_STORE
