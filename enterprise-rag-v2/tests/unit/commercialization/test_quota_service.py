import pytest
from unittest.mock import AsyncMock, MagicMock

from apps.commercialization.models import QuotaExceededError
from apps.commercialization.services.quota_service import QuotaService


def _realtime_rows(documents: int, users: int = 1, workspaces: int = 1, bytes_sum: int = 0):
    return [
        {"c": users},
        {"c": workspaces},
        {"c": documents},
        {"bytes_sum": bytes_sum},
    ]


@pytest.fixture
def quota_service():
    db = MagicMock()
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.hget = AsyncMock(return_value="0")
    redis.hincrby = AsyncMock(return_value=0)
    redis.hset = AsyncMock(return_value=True)
    redis.hgetall = AsyncMock(return_value={})
    pipe = MagicMock()
    pipe.hset.return_value = pipe
    pipe.expire.return_value = pipe
    pipe.execute = AsyncMock(return_value=[True] * 16)
    redis.pipeline = AsyncMock(return_value=pipe)
    return QuotaService(db, redis)


@pytest.mark.asyncio
async def test_default_resources_are_unlimited(quota_service):
    quota_service.db.fetch_one = AsyncMock(side_effect=[None] + _realtime_rows(documents=100_000))
    is_ok, current, limit, _ = await quota_service.check_quota("tenant", "documents")
    assert is_ok is True
    assert current == 100_000
    assert limit == -1


@pytest.mark.asyncio
async def test_deployment_override_blocks_overage(quota_service):
    quota_service._get_override_limit = AsyncMock(return_value=10)
    quota_service._get_realtime_usage = AsyncMock(return_value={"documents": 10})
    with pytest.raises(QuotaExceededError):
        await quota_service.check_quota("tenant", "documents")


@pytest.mark.asyncio
async def test_increment_usage(quota_service):
    quota_service.redis.hincrby = AsyncMock(return_value=5)
    new_value = await quota_service.increment_usage("tenant", "documents", 2)
    assert new_value == 5
    quota_service.redis.hincrby.assert_awaited_once_with("quota:tenant", "documents", 2)


@pytest.mark.asyncio
async def test_decrement_usage_clamps_to_zero(quota_service):
    quota_service.redis.hincrby = AsyncMock(return_value=-1)
    assert await quota_service.decrement_usage("tenant", "documents", 5) == 0
    quota_service.redis.hset.assert_awaited_once_with("quota:tenant", "documents", 0)


@pytest.mark.asyncio
async def test_init_records_unlimited_defaults(quota_service):
    result = await quota_service.init_free_tier("tenant", "person@example.com")
    assert result["success"] is True
    assert result["limits"]["documents"] == -1
    assert result["limits"]["storage_mb"] == -1


@pytest.mark.asyncio
async def test_reset_monthly_quotas(quota_service):
    await quota_service.reset_monthly_quotas("tenant")
    quota_service.redis.pipeline.assert_awaited_once()
