from sqlalchemy.exc import SQLAlchemyError
"""
会话审计日志记录器

负责记录所有会话相关的敏感操作，包括：
- 会话访问（查看）
- 可见性变更
- 管理员操作

审计日志用于安全合规和问题排查，必须确保完整性和不可篡改性。
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import json
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """
    审计日志记录器
    
    功能：
    1. 记录会话访问事件
    2. 记录可见性变更事件
    3. 记录管理员操作事件
    4. 异步写入，不阻塞主流程
    """
    
    def __init__(self):
        self._session = None
    
    async def log_conversation_access(
        self,
        user_id: str,
        conversation_id: UUID,
        action: str = "view",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session=None
    ) -> None:
        """记录会话访问事件
        
        Args:
            user_id: 用户ID
            conversation_id: 会话ID
            action: 操作类型（view/update/delete/admin_view）
            ip_address: 客户端IP地址
            user_agent: 用户代理字符串
            session: 数据库会话（可选）
        """
        try:
            await self._write_log(
                user_id=user_id,
                resource_type="conversation",
                resource_id=str(conversation_id),
                action=action,
                details={
                    "ip_address": ip_address,
                    "user_agent": user_agent[:200] if user_agent else None
                },
                session=session
            )
            
            logger.info(f"Audit: User {user_id} {action} conversation {conversation_id}")
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.error(f"Failed to log conversation access: {e}")
    
    async def log_visibility_change(
        self,
        user_id: str,
        conversation_id: UUID,
        old_visibility: str,
        new_visibility: str,
        ip_address: Optional[str] = None,
        session=None
    ) -> None:
        """记录可见性变更事件
        
        Args:
            user_id: 操作者用户ID
            conversation_id: 会话ID
            old_visibility: 原始可见性级别
            new_visibility: 新的可见性级别
            ip_address: 客户端IP地址
            session: 数据库会话（可选）
        """
        try:
            await self._write_log(
                user_id=user_id,
                resource_type="conversation",
                resource_id=str(conversation_id),
                action="visibility_change",
                details={
                    "old_visibility": old_visibility,
                    "new_visibility": new_visibility,
                    "ip_address": ip_address
                },
                session=session
            )
            
            logger.info(
                f"Audit: User {user_id} changed conversation {conversation_id} "
                f"visibility from {old_visibility} to {new_visibility}"
            )
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.error(f"Failed to log visibility change: {e}")
    
    async def log_admin_action(
        self,
        admin_user_id: str,
        conversation_id: UUID,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        target_user_id: Optional[str] = None,
        session=None
    ) -> None:
        """记录管理员操作事件
        
        Args:
            admin_user_id: 管理员用户ID
            conversation_id: 会话ID
            action: 操作类型（admin_view/admin_update/admin_delete）
            details: 额外详情
            ip_address: 客户端IP地址
            target_user_id: 目标用户ID（如果适用）
            session: 数据库会话（可选）
        """
        try:
            audit_details = {
                **(details or {}),
                "ip_address": ip_address,
                "target_user_id": target_user_id,
                "is_admin_action": True
            }
            
            await self._write_log(
                user_id=admin_user_id,
                resource_type="conversation",
                resource_id=str(conversation_id),
                action=action,
                details=audit_details,
                session=session
            )
            
            logger.info(
                f"Audit: Admin {admin_user_id} performed {action} on conversation {conversation_id}"
            )
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.error(f"Failed to log admin action: {e}")
    
    async def _write_log(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        session=None
    ) -> None:
        """写入审计日志到数据库"""
        
        # 尝试使用提供的session或创建新的session
        if session is None:
            from infrastructure.database.session import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                await self._insert_log_record(
                    session=session,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    details=details
                )
        else:
            await self._insert_log_record(
                session=session,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                details=details
            )
    
    async def _insert_log_record(
        self,
        session,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """插入日志记录到数据库"""
        from sqlalchemy import text
        
        # 构建SQL语句
        sql = """
            INSERT INTO audit_logs (
                id, user_id, resource_type, resource_id, 
                action, details, ip_address, created_at
            ) VALUES (
                gen_random_uuid(), :user_id, :resource_type, :resource_id,
                :action, :details::jsonb, 
                COALESCE(:details->>'ip_address', NULL),
                NOW()
            )
        """
        
        params = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "details": json.dumps(details) if details else "{}"
        }
        
        await session.execute(text(sql), params)
        await session.commit()


# 全局单例实例
audit_logger = AuditLogger()


async def get_audit_logger() -> AuditLogger:
    """获取审计日志记录器实例"""
    return audit_logger