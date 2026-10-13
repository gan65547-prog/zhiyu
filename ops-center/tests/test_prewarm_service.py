import pytest

from app.services import prewarm_service


@pytest.mark.asyncio
async def test_prewarm_all_success():
    class _Gateway:
        async def request(self, method, path, **kwargs):  # noqa: ANN001
            return {"success": True}

    result = await prewarm_service.run_startup_prewarm(gateway_factory=_Gateway)
    assert result["total"] == 3
    assert result["warmed"] == 3
    assert result["failed"] == 0
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_prewarm_partial_failure():
    class _Gateway:
        async def request(self, method, path, **kwargs):  # noqa: ANN001
            if path.endswith("/operations"):
                raise RuntimeError("upstream down")
            return {"success": True}

    result = await prewarm_service.run_startup_prewarm(gateway_factory=_Gateway)
    assert result["total"] == 3
    assert result["warmed"] == 2
    assert result["failed"] == 1
    assert result["ok"] is False
