from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    payload: dict[str, Any]
    expires_at: float
    snapshot_at: float


class ReadCacheService:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._store.get(key)
        if not item:
            return None
        now = time.time()
        if item.expires_at <= now:
            self._store.pop(key, None)
            return None
        payload = dict(item.payload)
        meta = dict(payload.get("meta") or {})
        meta["data_source"] = "cache"
        meta["snapshot_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(item.snapshot_at))
        payload["meta"] = meta
        return payload

    def set(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        now = time.time()
        self._store[key] = CacheEntry(
            payload=dict(payload),
            expires_at=now + max(1, ttl_seconds),
            snapshot_at=now,
        )

    def invalidate_all(self) -> int:
        """清空只读网关缓存（熔断恢复或运维主动失效后强制回源）。"""
        n = len(self._store)
        self._store.clear()
        return n


READ_CACHE = ReadCacheService()
