import pytest

from services.ops.cache_invalidation import invalidate_ops_caches


class _FakeRedis:
    def __init__(self) -> None:
        self.keys: dict[str, str] = {}
        self.deleted: list[str] = []

    async def delete(self, key: str) -> bool:
        if key in self.keys:
            del self.keys[key]
            self.deleted.append(key)
            return True
        return False

    async def clear_pattern(self, pattern: str) -> int:
        if pattern == "quota_override:*":
            n = len([k for k in list(self.keys.keys()) if k.startswith("quota_override:")])
            for k in list(self.keys.keys()):
                if k.startswith("quota_override:"):
                    del self.keys[k]
            return n
        return 0


@pytest.mark.asyncio
async def test_invalidate_quota_overrides_single_dimension():
    r = _FakeRedis()
    r.keys["quota_override:t1:documents"] = "1"
    r.keys["quota_override:t1:users"] = "1"

    await invalidate_ops_caches(
        r,  # type: ignore[arg-type]
        scopes=["quota_overrides"],
        tenant_id="t1",
        dimension="documents",
    )

    assert "quota_override:t1:documents" not in r.keys
    assert "quota_override:t1:users" in r.keys
