"""
备份服务实现
"""

import os
import json
import asyncio
import tarfile
import tempfile
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import Tenant, User, Workspace, Dataset, Document
from infrastructure.backup.storage import LocalBackupStorage, S3BackupStorage
from services.interfaces.backup_service import (
    BackupServiceInterface,
    BackupStorageInterface,
    BackupEntry,
    RestoreEntry,
    BackupStatus
)


class BackupServiceImpl(BackupServiceInterface):
    """备份服务实现"""

    def __init__(
        self,
        session: AsyncSession,
        storage: Optional[BackupStorageInterface] = None
    ):
        self.session = session
        self.storage = storage or LocalBackupStorage()
        self._backup_records: Dict[str, BackupEntry] = {}

    async def create_full_backup(self, tenant_id: UUID) -> BackupEntry:
        """创建全量备份"""
        backup_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        backup_entry = BackupEntry(
            id=backup_id,
            backup_type="full",
            status=BackupStatus.IN_PROGRESS,
            created_at=created_at
        )

        self._backup_records[backup_id] = backup_entry

        try:
            backup_data = await self._collect_tenant_data(tenant_id)

            compressed_data = await self._compress_data(backup_data)

            file_path = await self.storage.upload(backup_id, compressed_data)

            backup_entry.status = BackupStatus.COMPLETED
            backup_entry.completed_at = datetime.now(timezone.utc)
            backup_entry.file_path = file_path
            backup_entry.size_bytes = len(compressed_data)

            return backup_entry

        except (RuntimeError, ValueError, TypeError, OSError, tarfile.TarError, json.JSONDecodeError) as e:
            backup_entry.status = BackupStatus.FAILED
            backup_entry.error_message = str(e)
            return backup_entry

    async def create_incremental_backup(
        self,
        tenant_id: UUID,
        base_backup_id: str
    ) -> BackupEntry:
        """创建增量备份"""
        backup_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        backup_entry = BackupEntry(
            id=backup_id,
            backup_type="incremental",
            status=BackupStatus.IN_PROGRESS,
            created_at=created_at,
            metadata={"base_backup_id": base_backup_id}
        )

        self._backup_records[backup_id] = backup_entry

        try:
            backup_data = await self._collect_incremental_data(tenant_id, base_backup_id)

            compressed_data = await self._compress_data(backup_data)

            file_path = await self.storage.upload(backup_id, compressed_data)

            backup_entry.status = BackupStatus.COMPLETED
            backup_entry.completed_at = datetime.now(timezone.utc)
            backup_entry.file_path = file_path
            backup_entry.size_bytes = len(compressed_data)

            return backup_entry

        except (RuntimeError, ValueError, TypeError, OSError, tarfile.TarError, json.JSONDecodeError) as e:
            backup_entry.status = BackupStatus.FAILED
            backup_entry.error_message = str(e)
            return backup_entry

    async def restore_from_backup(
        self,
        backup_id: str,
        target_tenant_id: UUID
    ) -> RestoreEntry:
        """从备份恢复"""
        restore_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        restore_entry = RestoreEntry(
            id=restore_id,
            backup_id=backup_id,
            status=BackupStatus.IN_PROGRESS,
            created_at=created_at
        )

        try:
            backup_data = await self.storage.download(backup_id)
            if not backup_data:
                raise Exception(f"Backup {backup_id} not found")

            extracted_data = await self._decompress_data(backup_data)

            await self._restore_tenant_data(target_tenant_id, extracted_data)

            restore_entry.status = BackupStatus.COMPLETED
            restore_entry.completed_at = datetime.now(timezone.utc)

            return restore_entry

        except (RuntimeError, ValueError, TypeError, OSError, tarfile.TarError, json.JSONDecodeError) as e:
            restore_entry.status = BackupStatus.FAILED
            restore_entry.error_message = str(e)
            return restore_entry

    async def list_backups(
        self,
        tenant_id: Optional[UUID] = None,
        backup_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[BackupEntry]:
        """列出备份"""
        backups = list(self._backup_records.values())

        if tenant_id:
            backups = [b for b in backups if b.metadata.get("tenant_id") == str(tenant_id)]

        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]

        if status:
            backups = [b for b in backups if b.status == status]

        return backups

    async def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        if backup_id not in self._backup_records:
            return False

        success = await self.storage.delete(backup_id)

        if success:
            del self._backup_records[backup_id]

        return success

    async def get_backup_status(self, backup_id: str) -> Optional[BackupEntry]:
        """获取备份状态"""
        return self._backup_records.get(backup_id)

    async def schedule_backup(
        self,
        tenant_id: UUID,
        schedule_type: str,
        interval_hours: int = 24
    ) -> str:
        """设置备份计划"""
        schedule_id = str(uuid4())

        self._backup_records[f"schedule_{schedule_id}"] = BackupEntry(
            id=schedule_id,
            backup_type=schedule_type,
            status=BackupStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata={
                "tenant_id": str(tenant_id),
                "interval_hours": interval_hours,
                "schedule_id": schedule_id
            }
        )

        return schedule_id

    async def _collect_tenant_data(self, tenant_id: UUID) -> Dict[str, Any]:
        """收集租户数据"""
        data = {
            "tenant_id": str(tenant_id),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "tables": {}
        }

        tables_to_backup = [Tenant, User, Workspace, Dataset, Document]

        for model in tables_to_backup:
            table_name = model.__tablename__
            result = await self.session.execute(
                select(model).where(model.tenant_id == tenant_id)
            )
            records = result.scalars().all()

            data["tables"][table_name] = [
                self._model_to_dict(record) for record in records
            ]

        return data

    async def _collect_incremental_data(
        self,
        tenant_id: UUID,
        base_backup_id: str
    ) -> Dict[str, Any]:
        """收集增量数据"""
        data = await self._collect_tenant_data(tenant_id)
        data["backup_type"] = "incremental"
        data["base_backup_id"] = base_backup_id
        return data

    async def _compress_data(self, data: Dict[str, Any]) -> bytes:
        """压缩数据"""
        def _compress():
            json_data = json.dumps(data, default=str).encode("utf-8")

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                with tarfile.open(fileobj=tmp, mode="w:gz") as tar:
                    tarinfo = tarfile.TarInfo(name="backup.json")
                    tarinfo.size = len(json_data)
                    tar.addfile(tarinfo, file=tempfile.BytesIO(json_data))

                tmp.seek(0)
                return tmp.read()

        return await asyncio.get_event_loop().run_in_executor(None, _compress)

    async def _decompress_data(self, compressed_data: bytes) -> Dict[str, Any]:
        """解压数据"""
        def _decompress():
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(compressed_data)
                tmp.seek(0)

                with tarfile.open(fileobj=tmp, mode="r:gz") as tar:
                    member = tar.extractfile("backup.json")
                    if member:
                        json_data = member.read()
                        return json.loads(json_data.decode("utf-8"))

            return {}

        return await asyncio.get_event_loop().run_in_executor(None, _decompress)

    async def _restore_tenant_data(
        self,
        tenant_id: UUID,
        data: Dict[str, Any]
    ) -> None:
        """恢复租户数据"""
        pass

    def _model_to_dict(self, model) -> Dict[str, Any]:
        """将模型转换为字典"""
        result = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            if hasattr(value, "value"):
                value = value.value
            result[column.name] = value
        return result
