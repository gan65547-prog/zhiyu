"""
依赖注入容器

管理系统组件的依赖关系和生命周期
"""

from typing import Dict, Any, TypeVar, Type, Callable, Optional, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings


T = TypeVar('T')


class Container:
    """依赖注入容器"""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._session_factory: Optional[Callable] = None

    def register_singleton(self, interface: Type[T], implementation: T) -> None:
        """注册单例服务"""
        key = self._get_key(interface)
        self._singletons[key] = implementation

    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """注册工厂方法"""
        key = self._get_key(interface)
        self._factories[key] = factory

    def register_instance(self, interface: Type[T], instance: T) -> None:
        """注册实例"""
        key = self._get_key(interface)
        self._services[key] = instance

    def register_session_factory(self, factory: Callable) -> None:
        """注册会话工厂"""
        self._session_factory = factory

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        if self._session_factory:
            async with self._session_factory() as session:
                yield session
        else:
            raise RuntimeError("Session factory not registered")

    def get(self, interface: Type[T]) -> T:
        """获取服务实例"""
        key = self._get_key(interface)

        if key in self._singletons:
            return self._singletons[key]

        if key in self._services:
            return self._services[key]

        if key in self._factories:
            return self._factories[key]()

        raise ValueError(f"Service not registered: {interface}")

    def _get_key(self, interface: Type) -> str:
        """获取服务键名"""
        return f"{interface.__module__}.{interface.__name__}"

    async def init_services(self) -> None:
        """初始化所有服务"""
        from infrastructure.repositories import (
            TenantRepositoryImpl,
            UserRepositoryImpl,
            WorkspaceRepositoryImpl,
            WorkspaceMemberRepositoryImpl,
            DatasetRepositoryImpl,
            DocumentRepositoryImpl,
            DocumentChunkRepositoryImpl,
            ConversationRepositoryImpl,
            MessageRepositoryImpl,
        )
        from services.impl import (
            AuthServiceImpl,
            TenantServiceImpl,
            WorkspaceServiceImpl,
            DatasetServiceImpl,
            DocumentServiceImpl,
            ChatServiceImpl,
        )

        self._repositories = {
            "tenant": TenantRepositoryImpl,
            "user": UserRepositoryImpl,
            "workspace": WorkspaceRepositoryImpl,
            "workspace_member": WorkspaceMemberRepositoryImpl,
            "dataset": DatasetRepositoryImpl,
            "document": DocumentRepositoryImpl,
            "document_chunk": DocumentChunkRepositoryImpl,
            "conversation": ConversationRepositoryImpl,
            "message": MessageRepositoryImpl,
        }

        self._service_impls = {
            "auth": AuthServiceImpl,
            "tenant": TenantServiceImpl,
            "workspace": WorkspaceServiceImpl,
            "dataset": DatasetServiceImpl,
            "document": DocumentServiceImpl,
            "chat": ChatServiceImpl,
        }

    def get_repository(self, name: str):
        """获取Repository类"""
        return self._repositories.get(name)

    def get_service_impl(self, name: str):
        """获取Service实现类"""
        return self._service_impls.get(name)


container = Container()


def get_container() -> Container:
    """获取全局容器"""
    return container
