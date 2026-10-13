"""
备份服务接口定义
"""

from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime


class BackupStatus:
    """备份状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class BackupEntry:
    """备份记录"""
    def __init__(
        self,
        id: str,
        backup_type: str,
        status: str,
        created_at: datetime,
        completed_at: Optional[datetime] = None,
        size_bytes: int = 0,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        self.id = id
        self.backup_type = backup_type
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at
        self.size_bytes = size_bytes
        self.file_path = file_path
        self.metadata = metadata or {}
        self.error_message = error_message


class RestoreEntry:
    """恢复记录"""
    def __init__(
        self,
        id: str,
        backup_id: str,
        status: str,
        created_at: datetime,
        completed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        self.id = id
        self.backup_id = backup_id
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at
        self.metadata = metadata or {}
        self.error_message = error_message


class BackupServiceInterface(ABC):
    """备份服务接口"""

    @abstractmethod
    async def create_full_backup(self, tenant_id: UUID) -> BackupEntry:
        """创建全量备份"""
        pass

    @abstractmethod
    async def create_incremental_backup(self, tenant_id: UUID, base_backup_id: str) -> BackupEntry:
        """创建增量备份"""
        pass

    @abstractmethod
    async def restore_from_backup(self, backup_id: str, target_tenant_id: UUID) -> RestoreEntry:
        """从备份恢复"""
        pass

    @abstractmethod
    async def list_backups(
        self,
        tenant_id: Optional[UUID] = None,
        backup_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[BackupEntry]:
        """列出备份"""
        pass

    @abstractmethod
    async def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        pass

    @abstractmethod
    async def get_backup_status(self, backup_id: str) -> Optional[BackupEntry]:
        """获取备份状态"""
        pass

    @abstractmethod
    async def schedule_backup(
        self,
        tenant_id: UUID,
        schedule_type: str,
        interval_hours: int = 24
    ) -> str:
        """设置备份计划"""
        pass


class BackupStorageInterface(ABC):
    """备份存储接口"""

    @abstractmethod
    async def upload(self, backup_id: str, data: bytes) -> str:
        """上传备份"""
        pass

    @abstractmethod
    async def download(self, backup_id: str) -> Optional[bytes]:
        """下载备份"""
        pass

    @abstractmethod
    async def delete(self, backup_id: str) -> bool:
        """删除备份"""
        pass

    @abstractmethod
    async def exists(self, backup_id: str) -> bool:
        """检查备份是否存在"""
        pass

    @abstractmethod
    async def get_size(self, backup_id: str) -> int:
        """获取备份大小"""
        pass
