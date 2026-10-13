"""
审计服务接口定义
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from services.audit.service import AuditAction  # 统一复用实际实现侧枚举，避免双版本漂移


class ResourceType(str, Enum):
    """资源类型枚举"""
    USER = "user"
    TENANT = "tenant"
    WORKSPACE = "workspace"
    DATASET = "dataset"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    MESSAGE = "message"
    API_KEY = "api_key"
    OAUTH_ACCOUNT = "oauth_account"
    BACKUP = "backup"
    CONFIG = "config"


class AuditLogEntry:
    """审计日志条目"""

    def __init__(
        self,
        id: str,
        action: AuditAction,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.details = details or {}
        self.status = status
        self.error_message = error_message
        self.created_at = created_at or datetime.now(timezone.utc)


class AuditServiceInterface(ABC):
    """审计服务接口"""

    @abstractmethod
    async def log_security_event(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        记录安全事件

        Args:
            action: 动作类型
            user_id: 用户ID
            ip_address: IP地址
            details: 详细信息

        Returns:
            日志ID
        """
        pass

    @abstractmethod
    async def log_data_access(
        self,
        action: AuditAction,
        resource_type: ResourceType,
        resource_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        记录数据访问

        Args:
            action: 动作类型
            resource_type: 资源类型
            resource_id: 资源ID
            user_id: 用户ID
            tenant_id: 租户ID
            workspace_id: 工作空间ID
            ip_address: IP地址
            details: 详细信息

        Returns:
            日志ID
        """
        pass

    @abstractmethod
    async def log_authentication(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> str:
        """
        记录认证事件

        Args:
            action: 动作类型
            user_id: 用户ID
            username: 用户名
            ip_address: IP地址
            status: 状态
            error_message: 错误信息

        Returns:
            日志ID
        """
        pass

    @abstractmethod
    async def query_logs(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[ResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """
        查询审计日志

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            workspace_id: 工作空间ID
            action: 动作类型
            resource_type: 资源类型
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量
            offset: 偏移量

        Returns:
            审计日志列表
        """
        pass

    @abstractmethod
    async def get_security_alerts(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """
        获取安全告警

        Args:
            tenant_id: 租户ID
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量

        Returns:
            安全告警列表
        """
        pass

    @abstractmethod
    async def export_logs(
        self,
        start_time: datetime,
        end_time: datetime,
        format: str = "json"
    ) -> bytes:
        """
        导出审计日志

        Args:
            start_time: 开始时间
            end_time: 结束时间
            format: 导出格式

        Returns:
            导出数据
        """
        pass
