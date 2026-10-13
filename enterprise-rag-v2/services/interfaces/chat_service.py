"""
对话服务接口

定义对话和RAG查询相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncIterator
from uuid import UUID
from core.value_objects.pagination import Pagination, Page

# 导入会话可见性枚举
try:
    from infrastructure.database.models import ConversationVisibility
except ImportError:
    # 如果模型未加载，使用字符串类型作为后备
    from enum import Enum
    
    class ConversationVisibility(str, Enum):
        PRIVATE = "private"
        WORKSPACE = "workspace"
        TENANT = "tenant"


class ChatService(ABC):
    """对话服务抽象接口"""
    
    @abstractmethod
    async def chat(
        self,
        dataset_id: Optional[UUID],
        query: str,
        dataset_ids: Optional[List[UUID]] = None,
        conversation_id: Optional[UUID] = None,
        history: Optional[List[Dict[str, str]]] = None,
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> dict:
        """
        发送对话请求
        
        Args:
            dataset_id: 数据集ID
            query: 用户查询
            conversation_id: 会话ID
            history: 历史消息
            retrieval_mode: 检索模式
            top_k: 返回top-k文档
            temperature: 生成温度
            max_tokens: 最大token数
            
        Returns:
            对话响应
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        dataset_id: UUID,
        query: str,
        conversation_id: Optional[UUID] = None,
        history: Optional[List[Dict[str, str]]] = None,
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[dict]:
        """
        流式对话请求
        
        Args:
            dataset_id: 数据集ID
            query: 用户查询
            conversation_id: 会话ID
            history: 历史消息
            retrieval_mode: 检索模式
            top_k: 返回top-k文档
            temperature: 生成温度
            max_tokens: 最大token数
            
        Yields:
            对话响应片段
        """
        pass
    
    @abstractmethod
    async def create_conversation(
        self,
        dataset_id: UUID,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        visibility: ConversationVisibility = ConversationVisibility.PRIVATE,
        workspace_id: Optional[UUID] = None
    ) -> dict:
        """
        创建会话（支持可见性设置）
        
        Args:
            dataset_id: 数据集ID
            user_id: 用户ID
            title: 会话标题
            metadata: 元数据
            visibility: 可见性级别（默认PRIVATE）
            workspace_id: 工作空间ID（可选）
            
        Returns:
            会话信息
        """
        pass
    
    @abstractmethod
    async def get_conversation(
        self,
        conversation_id: UUID
    ) -> Optional[dict]:
        """
        获取会话详情
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            会话信息或None
        """
        pass
    
    @abstractmethod
    async def update_conversation(
        self,
        conversation_id: UUID,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        visibility: Optional[ConversationVisibility] = None
    ) -> dict:
        """
        更新会话（支持可见性变更）
        
        Args:
            conversation_id: 会话ID
            title: 会话标题
            metadata: 元数据
            visibility: 新的可见性级别
            
        Returns:
            更新后的会话信息
        """
        pass
    
    @abstractmethod
    async def delete_conversation(
        self,
        conversation_id: UUID
    ) -> bool:
        """
        删除会话
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def list_conversations(
        self,
        dataset_id: Optional[UUID] = None,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """
        查询会话列表（向后兼容，不包含权限过滤）
        
        Args:
            dataset_id: 数据集ID
            keyword: 关键词搜索
            pagination: 分页参数
            
        Returns:
            分页的会话列表
        """
        pass
    
    @abstractmethod
    async def list_conversations_with_permissions(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """
        查询会话列表（基于权限过滤）
        
        根据用户角色和会话可见性返回用户有权访问的会话列表。
        支持按可见性、工作空间、数据集等条件过滤。
        
        Args:
            user_id: 用户ID
            filters: 过滤条件
                - visibility: 可见性级别过滤
                - workspace_id: 工作空间ID过滤
                - dataset_id: 数据集ID过滤
                - keyword: 关键词搜索
            pagination: 分页参数
            
        Returns:
            分页的会话列表（只包含用户有权访问的会话）
        """
        pass
    
    @abstractmethod
    async def update_conversation_visibility(
        self,
        conversation_id: UUID,
        user_id: str,
        new_visibility: ConversationVisibility
    ) -> dict:
        """
        更新会话可见性级别
        
        只有创建者或管理员可以修改可见性。
        修改后会立即生效：
        - 从共享变为私有：其他用户立即失去访问权限
        - 从私有变为共享：符合条件的用户立即获得访问权限
        
        Args:
            conversation_id: 会话ID
            user_id: 操作者用户ID
            new_visibility: 新的可见性级别
            
        Returns:
            更新后的会话信息
            
        Raises:
            PermissionError: 无权修改
            ValueError: 无效的可见性值
        """
        pass
    
    @abstractmethod
    async def get_conversation_messages(
        self,
        conversation_id: UUID
    ) -> List[dict]:
        """
        获取会话消息历史
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            消息列表
        """
        pass
