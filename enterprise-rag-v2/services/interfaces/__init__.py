"""
Service层接口定义

定义业务服务的抽象接口
"""

from .auth_service import AuthService
from .tenant_service import TenantService
from .workspace_service import WorkspaceService
from .dataset_service import DatasetService
from .document_service import DocumentService
from .chat_service import ChatService

__all__ = [
    "AuthService",
    "TenantService",
    "WorkspaceService",
    "DatasetService",
    "DocumentService",
    "ChatService",
]
