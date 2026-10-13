import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.commercialization.services.quota_service import QuotaService


@pytest.mark.asyncio
async def test_check_quota_uses_override_limit_from_cache():
    mock_db = MagicMock()
    mock_redis = MagicMock()

    # 覆盖值命中缓存：documents 上限设置为 2
    mock_redis.get = AsyncMock(
        return_value=json.dumps({"tenant_id": "t1", "dimension": "documents", "override_value": 2})
    )
    mock_db.fetch_one = AsyncMock(return_value=None)

    svc = QuotaService(mock_db, mock_redis)
    svc._get_realtime_usage = AsyncMock(return_value={"documents": 3})
    with pytest.raises(Exception) as exc:
        await svc.check_quota("t1", "documents")

    assert "配额" in str(exc.value)


@pytest.mark.asyncio
async def test_get_usage_info_applies_override_limit():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.get = AsyncMock(return_value=None)

    mock_db.fetch_one = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    svc = QuotaService(mock_db, mock_redis)
    svc._get_override_limit = AsyncMock(side_effect=[3] + [None] * 8)
    svc._get_realtime_usage = AsyncMock(
        return_value={"users": 1, "workspaces": 1, "documents": 4, "storage_mb": 0}
    )
    usage = await svc.get_usage_info("t1")

    assert usage["limits"]["users"] == 3
