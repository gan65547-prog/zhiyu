import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.commercialization.services.quota_override_service import QuotaOverrideService


@pytest.mark.asyncio
async def test_get_override_ignores_expired_cache():
    db = MagicMock()
    redis = MagicMock()
    expired = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {"tenant_id": "t1", "dimension": "documents", "override_value": 100, "expires_at": expired}
        )
    )
    redis.delete = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)

    svc = QuotaOverrideService(db, redis)
    result = await svc.get_override("t1", "documents")

    assert result is None
    redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_override_cache_ttl_follows_expires_at():
    db = MagicMock()
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    expires_at = datetime.utcnow() + timedelta(seconds=120)
    db.fetch_one = AsyncMock(
        return_value={
            "tenant_id": "t1",
            "dimension": "documents",
            "override_value": 100,
            "reason": "temp",
            "expires_at": expires_at,
            "created_by": "ops",
        }
    )

    svc = QuotaOverrideService(db, redis)
    result = await svc.get_override("t1", "documents")

    assert result is not None
    assert result["override_value"] == 100
    assert redis.setex.await_count == 1
    ttl = redis.setex.await_args.args[1]
    assert 1 <= ttl <= 300
