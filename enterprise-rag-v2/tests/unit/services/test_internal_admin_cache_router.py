from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.internal_admin.routers.cache import invalidate_cache, CacheInvalidateBody


@pytest.mark.asyncio
async def test_invalidate_cache_success():
    mock_redis = MagicMock()
    mock_redis.delete = AsyncMock(return_value=True)
    mock_redis.clear_pattern = AsyncMock(return_value=3)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                quota_service=SimpleNamespace(redis=mock_redis),
            )
        )
    )
    identity = {
        "operation_id": "op_cache_1",
        "operator": "tester",
        "request_id": "req_1",
        "client_ip": "127.0.0.1",
    }
    body = CacheInvalidateBody(scopes=["quota_overrides"], tenant_id="t1")

    with patch(
        "api.internal_admin.routers.cache.invalidate_ops_caches",
        new_callable=AsyncMock,
    ) as inv:
        inv.return_value = {"scopes": ["quota_overrides"], "deleted": {"quota_override_keys": 7}}
        result = await invalidate_cache(body, request, identity)

    assert result["success"] is True
    assert result["data"]["deleted"]["quota_override_keys"] == 7
    inv.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_cache_rejects_bad_dimension():
    mock_redis = MagicMock()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                quota_service=SimpleNamespace(redis=mock_redis),
            )
        )
    )
    identity = {
        "operation_id": "op_cache_1",
        "operator": "tester",
        "request_id": "req_1",
        "client_ip": "127.0.0.1",
    }
    body = CacheInvalidateBody(
        scopes=["quota_overrides"],
        tenant_id="t1",
        dimension="not_a_dimension",
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        await invalidate_cache(body, request, identity)
    assert ei.value.status_code == 400
    assert ei.value.detail["error"]["code"] == "INVALID_DIMENSION"
