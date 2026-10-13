from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4
import json


class QuotaOverrideService:
    """人工配额覆盖规则服务。"""

    def __init__(self, db, redis):
        self.db = db
        self.redis = redis

    @staticmethod
    def _cache_key(tenant_id: str, dimension: str) -> str:
        return f"quota_override:{tenant_id}:{dimension}"

    @staticmethod
    def _is_expired(expires_at: Optional[datetime]) -> bool:
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    async def get_override(self, tenant_id: str, dimension: str) -> Optional[dict[str, Any]]:
        """读取有效覆盖规则；过期规则自动忽略并清理缓存。"""
        cache_key = self._cache_key(tenant_id, dimension)
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                payload = json.loads(cached)
                expires_at_raw = payload.get("expires_at")
                expires_at = datetime.fromisoformat(expires_at_raw).replace(tzinfo=timezone.utc) if expires_at_raw else None
                if self._is_expired(expires_at):
                    await self.redis.delete(cache_key)
                    return None
                return payload
        except (RuntimeError, ValueError, TypeError, AttributeError):
            pass

        row = await self.db.fetch_one(
            """
            SELECT tenant_id, dimension, override_value, reason, expires_at, created_by
            FROM quota_overrides
            WHERE tenant_id = :tenant_id
              AND dimension = :dimension
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"tenant_id": tenant_id, "dimension": dimension},
        )
        if not row:
            return None

        data = dict(row)
        expires_at = data.get("expires_at")
        ttl = 300
        if expires_at:
            expires_at_aware = expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at
            seconds = int((expires_at_aware - datetime.now(timezone.utc)).total_seconds())
            ttl = max(1, min(300, seconds))
        await self.redis.setex(
            cache_key,
            ttl,
            json.dumps(
                {
                    "tenant_id": str(data["tenant_id"]),
                    "dimension": str(data["dimension"]),
                    "override_value": int(data["override_value"]),
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "reason": data.get("reason"),
                    "created_by": data.get("created_by"),
                },
                ensure_ascii=False,
            ),
        )
        return {
            "tenant_id": str(data["tenant_id"]),
            "dimension": str(data["dimension"]),
            "override_value": int(data["override_value"]),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "reason": data.get("reason"),
            "created_by": data.get("created_by"),
        }

    async def set_override(
        self,
        tenant_id: str,
        dimension: str,
        override_value: int,
        reason: str,
        created_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = await self.db.fetch_one(
            """
            SELECT id FROM quota_overrides
            WHERE tenant_id = :tenant_id
              AND dimension = :dimension
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            {"tenant_id": tenant_id, "dimension": dimension},
        )

        if row:
            await self.db.execute(
                """
                UPDATE quota_overrides
                SET override_value = :override_value,
                    reason = :reason,
                    expires_at = :expires_at,
                    created_by = :created_by,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                {
                    "id": str(row["id"]),
                    "override_value": override_value,
                    "reason": reason,
                    "expires_at": expires_at,
                    "created_by": created_by,
                    "updated_at": now,
                },
            )
        else:
            await self.db.execute(
                """
                INSERT INTO quota_overrides (
                    id, tenant_id, dimension, override_value, reason, expires_at, created_by, created_at, updated_at
                )
                VALUES (
                    :id, :tenant_id, :dimension, :override_value, :reason, :expires_at, :created_by, :created_at, :updated_at
                )
                """,
                {
                    "id": str(uuid4()),
                    "tenant_id": tenant_id,
                    "dimension": dimension,
                    "override_value": override_value,
                    "reason": reason,
                    "expires_at": expires_at,
                    "created_by": created_by,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        cache_key = self._cache_key(tenant_id, dimension)
        ttl = 300
        if expires_at:
            seconds = int((expires_at - now).total_seconds())
            ttl = max(1, min(300, seconds))
        await self.redis.setex(
            cache_key,
            ttl,
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "dimension": dimension,
                    "override_value": override_value,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
                ensure_ascii=False,
            ),
        )

        return {
            "tenant_id": tenant_id,
            "dimension": dimension,
            "override_value": override_value,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "reason": reason,
        }

