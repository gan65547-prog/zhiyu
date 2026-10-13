"""
本地文件备份存储实现
"""

import os
import asyncio
from typing import Optional
from pathlib import Path

from services.interfaces.backup_service import BackupStorageInterface
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class LocalBackupStorage(BackupStorageInterface):
    """本地文件系统备份存储"""

    def __init__(self, base_path: str = "/tmp/backups"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_backup_path(self, backup_id: str) -> Path:
        """获取备份文件路径"""
        return self.base_path / f"{backup_id}.tar.gz"

    async def upload(self, backup_id: str, data: bytes) -> str:
        """上传备份到本地文件系统"""
        file_path = self._get_backup_path(backup_id)

        def write_file():
            with open(file_path, "wb") as f:
                f.write(data)

        await asyncio.get_event_loop().run_in_executor(None, write_file)

        return str(file_path)

    async def download(self, backup_id: str) -> Optional[bytes]:
        """从本地文件系统下载备份"""
        file_path = self._get_backup_path(backup_id)

        if not file_path.exists():
            return None

        def read_file():
            with open(file_path, "rb") as f:
                return f.read()

        return await asyncio.get_event_loop().run_in_executor(None, read_file)

    async def delete(self, backup_id: str) -> bool:
        """从本地文件系统删除备份"""
        file_path = self._get_backup_path(backup_id)

        if not file_path.exists():
            return False

        def remove_file():
            os.remove(file_path)

        await asyncio.get_event_loop().run_in_executor(None, remove_file)
        return True

    async def exists(self, backup_id: str) -> bool:
        """检查备份是否存在"""
        return self._get_backup_path(backup_id).exists()

    async def get_size(self, backup_id: str) -> int:
        """获取备份文件大小"""
        file_path = self._get_backup_path(backup_id)

        if not file_path.exists():
            return 0

        return file_path.stat().st_size


class S3BackupStorage(BackupStorageInterface):
    """S3备份存储"""

    def __init__(
        self,
        bucket_name: str,
        access_key: str = None,
        secret_key: str = None,
        endpoint_url: str = None,
        region: str = "us-east-1"
    ):
        self.bucket_name = bucket_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint_url = endpoint_url
        self.region = region
        self._client = None

    async def _get_client(self):
        """获取S3客户端"""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    endpoint_url=self.endpoint_url,
                    region_name=self.region
                )
            except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                logger.warning("初始化 S3 客户端失败: %s", exc, exc_info=True)
                self._client = None
        return self._client

    async def upload(self, backup_id: str, data: bytes) -> str:
        """上传备份到S3"""
        client = await self._get_client()
        if not client:
            raise RuntimeError("S3 client not available")

        key = f"backups/{backup_id}.tar.gz"

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data
            )
        )

        return key

    async def download(self, backup_id: str) -> Optional[bytes]:
        """从S3下载备份"""
        client = await self._get_client()
        if not client:
            return None

        key = f"backups/{backup_id}.tar.gz"

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.get_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
            )
            return response["Body"].read()
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
            logger.warning("S3 下载备份失败: backup_id=%s error=%s", backup_id, exc, exc_info=True)
            return None

    async def delete(self, backup_id: str) -> bool:
        """从S3删除备份"""
        client = await self._get_client()
        if not client:
            return False

        key = f"backups/{backup_id}.tar.gz"

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
            )
            return True
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
            logger.warning("S3 删除备份失败: backup_id=%s error=%s", backup_id, exc, exc_info=True)
            return False

    async def exists(self, backup_id: str) -> bool:
        """检查S3备份是否存在"""
        client = await self._get_client()
        if not client:
            return False

        key = f"backups/{backup_id}.tar.gz"

        try:
            client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
            logger.warning("S3 检查备份存在失败: backup_id=%s error=%s", backup_id, exc, exc_info=True)
            return False

    async def get_size(self, backup_id: str) -> int:
        """获取S3备份大小"""
        client = await self._get_client()
        if not client:
            return 0

        key = f"backups/{backup_id}.tar.gz"

        try:
            response = client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response.get("ContentLength", 0)
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
            logger.warning("S3 获取备份大小失败: backup_id=%s error=%s", backup_id, exc, exc_info=True)
            return 0
