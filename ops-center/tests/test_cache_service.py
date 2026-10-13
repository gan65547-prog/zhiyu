from app.services.cache_service import ReadCacheService


def test_cache_set_and_get_marks_cache_source():
    cache = ReadCacheService()
    cache.set("k1", {"success": True, "data": [1], "meta": {"request_id": "r1"}}, 30)
    payload = cache.get("k1")
    assert payload is not None
    assert payload["meta"]["data_source"] == "cache"
    assert "snapshot_at" in payload["meta"]


def test_cache_expired_returns_none():
    cache = ReadCacheService()
    cache.set("k1", {"success": True}, 1)
    # 手动覆盖为已过期，避免 sleep
    cache._store["k1"].expires_at = 0  # noqa: SLF001
    assert cache.get("k1") is None


def test_invalidate_all_clears_store():
    cache = ReadCacheService()
    cache.set("a", {"x": 1}, 60)
    cache.set("b", {"y": 2}, 60)
    n = cache.invalidate_all()
    assert n == 2
    assert cache.get("a") is None
