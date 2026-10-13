"""对象存储抽象的本地实现。

生产环境可替换为 S3/MinIO 实现；业务层只依赖此接口，不拼接用户提供的路径。
"""

import asyncio
import os
from pathlib import Path
from typing import Optional


class LocalAssetStorage:
    """按租户和素材 ID 隔离的本地对象存储。"""

    def __init__(self, base_path: str | None = None):
        # Web and Celery run in separate containers. Store assets on the
        # compose-mounted runtime volume so workers can process files created
        # by the API process instead of each container's private /tmp.
        base_path = base_path or os.getenv(
            "ASSET_STORAGE_PATH",
            "/app/runtime/assets" if Path("/app").is_dir() else "/tmp/ganfy-assets",
        )
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _path(self, tenant_id: str, asset_id: str) -> Path:
        tenant = str(tenant_id)
        asset = str(asset_id)
        if any(part in {"", ".", ".."} or "/" in part or "\\" in part for part in (tenant, asset)):
            raise ValueError("非法素材存储标识")
        return self.base_path / tenant / f"{asset}.bin"

    def resolve_key(self, storage_key: str) -> Path:
        """解析由本存储实现生成的 key，并拒绝路径穿越。"""
        candidate = (self.base_path / storage_key).resolve()
        if self.base_path not in candidate.parents or candidate == self.base_path:
            raise ValueError("非法素材存储键")
        return candidate

    async def put(self, tenant_id: str, asset_id: str, content: bytes) -> str:
        path = self._path(tenant_id, asset_id)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(content)
            temporary.replace(path)

        await asyncio.to_thread(write)
        return str(path.relative_to(self.base_path))

    async def get(self, tenant_id: str, asset_id: str) -> Optional[bytes]:
        path = self._path(tenant_id, asset_id)
        if not path.is_file():
            return None
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, tenant_id: str, asset_id: str) -> bool:
        path = self._path(tenant_id, asset_id)
        if not path.is_file():
            return False
        await asyncio.to_thread(path.unlink)
        return True
