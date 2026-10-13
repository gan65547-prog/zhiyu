from unittest.mock import AsyncMock

import pytest

from infrastructure.monitoring.quota_override_metrics import refresh_quota_override_gauges


@pytest.mark.asyncio
async def test_refresh_quota_override_gauges_queries_counts():
    db = AsyncMock()
    db.fetch_one = AsyncMock(side_effect=[{"c": 2}, {"c": 5}])
    await refresh_quota_override_gauges(db)
    assert db.fetch_one.await_count == 2
