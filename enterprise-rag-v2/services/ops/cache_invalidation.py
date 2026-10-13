"""
运维相关缓存失效（内部接口与 Celery 任务共用）。
"""

from __future__ import annotations

from typing import Any

from infrastructure.cache.redis import RedisCache
from infrastructure.cache import CacheKeys
from apps.commercialization.config_quota import build_quota_key
from apps.commercialization.services.quota_service import QuotaService


async def invalidate_ops_caches(
    redis: RedisCache,
    *,
    scopes: list[str],
    tenant_id: str | None = None,
    dimension: str | None = None,
) -> dict[str, Any]:
    """
    按 scope 清理 Redis 中与运维/配额相关的缓存。

    scopes:
      - quota_overrides: quota_override:{tenant}:{dim}
      - quota_counters: quota:{tenant}（月度 API/对话等计数 Hash）
      - tenant_meta: tenant:{tenant}（租户摘要缓存键）
      - all: 上述全部（tenant_id 为空时仅对可全局清理的 scope 扫描键）
    """
    deleted: dict[str, int] = {}
    scopes_set = set(scopes)
    if "all" in scopes_set:
        scopes_set = {"quota_overrides", "quota_counters", "tenant_meta"}

    if "quota_overrides" in scopes_set:
        if tenant_id and dimension:
            key = f"quota_override:{tenant_id}:{dimension}"
            ok = await redis.delete(key)
            deleted["quota_override_keys"] = 1 if ok else 0
        elif tenant_id:
            n = 0
            for dim in QuotaService.DIMENSIONS:
                key = f"quota_override:{tenant_id}:{dim}"
                if await redis.delete(key):
                    n += 1
            deleted["quota_override_keys"] = n
        else:
            deleted["quota_override_keys"] = await redis.clear_pattern("quota_override:*")

    if "quota_counters" in scopes_set:
        if tenant_id:
            ok = await redis.delete(build_quota_key(tenant_id))
            deleted["quota_counters"] = 1 if ok else 0
        else:
            deleted["quota_counters"] = await redis.clear_pattern("quota:*")

    if "tenant_meta" in scopes_set:
        if tenant_id:
            ok = await redis.delete(CacheKeys.tenant(tenant_id))
            deleted["tenant_meta"] = 1 if ok else 0
        else:
            deleted["tenant_meta"] = await redis.clear_pattern("tenant:*")

    return {
        "scopes": sorted(scopes_set),
        "tenant_id": tenant_id,
        "dimension": dimension,
        "deleted": deleted,
    }
