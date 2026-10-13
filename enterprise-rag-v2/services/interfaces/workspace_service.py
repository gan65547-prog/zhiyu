"""
工作空间服务接口

定义工作空间管理相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from core.value_objects.pagination import Pagination, Page


class WorkspaceService(ABC):
    """工作空间服务抽象接口"""

    @property
    @abstractmethod
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        pass

    @abstractmethod
    async def create_workspace(
        self,
        tenant_id: UUID,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        创建工作空间

        Args:
            tenant_id: 租户ID
            name: 工作空间名称
            description: 描述
            metadata: 元数据

        Returns:
            工作空间信息字典
        """
        pass

    @abstractmethod
    async def get_workspace(
        self,
        workspace_id: UUID
    ) -> Optional[dict]:
        """
        获取工作空间详情

        Args:
            workspace_id: 工作空间ID

        Returns:
            工作空间信息字典或None
        """
        pass

    @abstractmethod
    async def update_workspace(
        self,
        workspace_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        更新工作空间

        Args:
            workspace_id: 工作空间ID
            name: 工作空间名称
            description: 描述
            metadata: 元数据

        Returns:
            更新后的工作空间信息
        """
        pass

    @abstractmethod
    async def delete_workspace(
        self,
        workspace_id: UUID
    ) -> bool:
        """
        删除工作空间

        Args:
            workspace_id: 工作空间ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def list_workspaces(
        self,
        tenant_id: UUID,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """
        查询工作空间列表

        Args:
            tenant_id: 租户ID
            keyword: 关键词搜索
            pagination: 分页参数

        Returns:
            分页的工作空间列表
        """
        pass

    @abstractmethod
    async def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "member"
    ) -> dict:
        """
        添加工作空间成员

        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID
            role: 角色

        Returns:
            成员信息
        """
        pass

    @abstractmethod
    async def remove_member(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        移除工作空间成员

        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def update_member_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str
    ) -> dict:
        """
        更新成员角色

        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID
            role: 新角色

        Returns:
            更新后的成员信息
        """
        pass

    @abstractmethod
    async def list_members(
        self,
        workspace_id: UUID
    ) -> List[dict]:
        """
        获取工作空间成员列表

        Args:
            workspace_id: 工作空间ID

        Returns:
            成员列表
        """
        pass

    @abstractmethod
    async def switch_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> dict:
        """
        切换用户当前工作空间

        Args:
            workspace_id: 工作空间ID
            user_id: 用户ID

        Returns:
            切换后的工作空间信息
        """
        pass

    @abstractmethod
    async def get_current_workspace(
        self,
        user_id: UUID,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        获取用户当前工作空间

        Args:
            user_id: 用户ID
            tenant_id: 当前 JWT 租户 ID；若与工作空间租户不一致则返回 None，避免脏数据导致异常

        Returns:
            当前工作空间信息或None
        """
        pass