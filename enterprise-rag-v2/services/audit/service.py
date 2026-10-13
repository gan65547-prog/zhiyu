"""
审计日志服务

提供操作日志、登录日志、数据变更日志功能
支持日志不可篡改机制
"""

import json
import hashlib
from datetime import timezone, datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel

from infrastructure.database.models import AuditLog, Base


class AuditAction(str, Enum):
    """审计操作类型"""
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    TOKEN_REFRESH = "token_refresh"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    TENANT_CREATE = "tenant_create"
    TENANT_UPDATE = "tenant_update"
    TENANT_DELETE = "tenant_delete"
    TENANT_CONTEXT_SWITCH = "tenant_context_switch"
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_UPDATE = "workspace_update"
    WORKSPACE_DELETE = "workspace_delete"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_DOWNLOAD = "document_download"
    CHAT_CREATE = "chat_create"
    CHAT_DELETE = "chat_delete"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    SECURITY_ALERT = "security_alert"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CSRF_VIOLATION = "csrf_violation"
    QUOTA_UPDATE = "quota_update"
    REINDEX_TRIGGER = "reindex_trigger"
    OPS_LOGIN = "ops_login"
    OPS_ROLE_GRANT = "ops_role_grant"
    OPS_ROLE_REVOKE = "ops_role_revoke"


class AuditLogCreate(BaseModel):
    """创建审计日志"""
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: AuditAction
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: UUID
    tenant_id: Optional[UUID]
    user_id: Optional[UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime


class AuditService:
    """审计日志服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _compute_hash(self, log_entry: AuditLog, prev_hash: Optional[str] = None) -> str:
        """计算日志哈希值，用于防篡改"""
        data = f"{log_entry.id}{log_entry.action}{log_entry.user_id}{log_entry.tenant_id}{log_entry.created_at.isoformat()}{prev_hash or ''}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def _get_last_hash(self) -> Optional[str]:
        """获取最后一条日志的哈希值"""
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1)
        result = await self.session.execute(query)
        last_log = result.scalar_one_or_none()
        return last_log.details.get("log_hash") if last_log and last_log.details else None

    async def log(
        self,
        action: AuditAction,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> Optional[AuditLog]:
        """记录审计日志"""
        try:
            prev_hash = await self._get_last_hash()
            
            log_details = details or {}
            log_hash = self._compute_hash(
                type('LogEntry', (), {
                    'id': uuid4(),
                    'action': action.value,
                    'user_id': user_id,
                    'tenant_id': tenant_id,
                    'created_at': datetime.now(timezone.utc)
                })(),
                prev_hash
            )
            log_details["log_hash"] = log_hash
            log_details["prev_hash"] = prev_hash

            log_entry = AuditLog(
                id=str(uuid4()),
                action=action.value,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=str(user_id) if user_id else None,
                tenant_id=str(tenant_id) if tenant_id else None,
                ip_address=ip_address,
                user_agent=user_agent,
                details=log_details,
                status=status,
                error_message=error_message,
                created_at=datetime.now(timezone.utc)
            )

            self.session.add(log_entry)
            await self.session.flush()
            await self.session.refresh(log_entry)

            return log_entry
        except (SQLAlchemyError, TypeError, ValueError):
            # 审计日志写入失败不影响主要业务逻辑
            return None

    async def log_login(
        self,
        user_id: Optional[UUID],
        tenant_id: Optional[UUID],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        username: Optional[str] = None
    ) -> AuditLog:
        """记录登录日志"""
        details = {"login_method": "password"}
        if username:
            details["username"] = username
            
        return await self.log(
            action=AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="user",
            resource_id=str(user_id) if user_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status="success" if success else "failed",
            error_message=error_message
        )

    async def log_logout(
        self,
        user_id: UUID,
        tenant_id: Optional[UUID],
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """记录登出日志"""
        return await self.log(
            action=AuditAction.LOGOUT,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="user",
            resource_id=str(user_id),
            ip_address=ip_address
        )

    async def log_data_change(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """记录数据变更日志"""
        return await self.log(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details={
                "old_value": old_value,
                "new_value": new_value
            },
            ip_address=ip_address
        )

    async def log_account_locked(
        self,
        user_id: Optional[UUID],
        tenant_id: Optional[UUID],
        ip_address: Optional[str] = None,
        reason: Optional[str] = None
    ) -> AuditLog:
        """记录账户锁定日志"""
        return await self.log(
            action=AuditAction.ACCOUNT_LOCKED,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="user",
            resource_id=str(user_id) if user_id else None,
            details={"reason": reason or "too_many_failed_attempts"},
            ip_address=ip_address,
            status="warning"
        )

    async def log_security_alert(
        self,
        alert_type: str,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """记录安全告警"""
        return await self.log(
            action=AuditAction.SECURITY_ALERT,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="security",
            details={"alert_type": alert_type, **(details or {})},
            ip_address=ip_address,
            status="warning"
        )

    async def get_user_logs(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """获取用户操作日志"""
        query = select(AuditLog).where(
            AuditLog.user_id == user_id
        ).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_tenant_logs(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """获取租户操作日志"""
        query = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id
        ).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_resource_logs(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100
    ) -> List[AuditLog]:
        """获取资源操作日志"""
        query = select(AuditLog).where(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id
        ).order_by(AuditLog.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_failed_login_attempts(
        self,
        ip_address: str,
        minutes: int = 15
    ) -> int:
        """获取指定时间内的失败登录次数（按IP）"""
        threshold = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        query = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == AuditAction.LOGIN_FAILED.value,
            AuditLog.ip_address == ip_address,
            AuditLog.created_at >= threshold
        )

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_failed_login_attempts_by_user(
        self,
        username: str,
        minutes: int = 15
    ) -> int:
        """获取指定时间内用户的失败登录次数"""
        threshold = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        query = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == AuditAction.LOGIN_FAILED.value,
            AuditLog.details["username"].as_string() == username,
            AuditLog.created_at >= threshold
        )

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def verify_log_integrity(self, log_id: UUID) -> bool:
        """验证日志完整性"""
        query = select(AuditLog).where(AuditLog.id == log_id)
        result = await self.session.execute(query)
        log_entry = result.scalar_one_or_none()
        
        if not log_entry or not log_entry.details:
            return False
            
        stored_hash = log_entry.details.get("log_hash")
        prev_hash = log_entry.details.get("prev_hash")
        expected_hash = self._compute_hash(log_entry, prev_hash)
        return stored_hash == expected_hash

    async def query_logs(
        self,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """查询审计日志"""
        query = select(AuditLog)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if tenant_id:
            query = query.where(AuditLog.tenant_id == tenant_id)
        if action:
            query = query.where(AuditLog.action == action.value)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if start_time:
            if start_time.tzinfo is not None:
                start_time = start_time.replace(tzinfo=None)
            query = query.where(AuditLog.created_at >= start_time)
        if end_time:
            if end_time.tzinfo is not None:
                end_time = end_time.replace(tzinfo=None)
            query = query.where(AuditLog.created_at <= end_time)
            
        query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
