import pytest

from infrastructure.storage.asset_storage import LocalAssetStorage


@pytest.mark.asyncio
async def test_local_asset_storage_is_tenant_scoped(tmp_path):
    storage = LocalAssetStorage(str(tmp_path))
    key = await storage.put("tenant-a", "asset-1", b"hello")

    assert key == "tenant-a/asset-1.bin"
    assert await storage.get("tenant-a", "asset-1") == b"hello"
    assert await storage.get("tenant-b", "asset-1") is None
    assert await storage.delete("tenant-a", "asset-1") is True
    assert await storage.get("tenant-a", "asset-1") is None
