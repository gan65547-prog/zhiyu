"""
数据集服务接口

定义数据集管理相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from core.value_objects.pagination import Pagination, Page


class DatasetService(ABC):
    """数据集服务抽象接口"""

    @property
    @abstractmethod
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        pass
    
    @abstractmethod
    async def create_dataset(
        self,
        workspace_id: UUID,
        name: str,
        description: Optional[str] = None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        创建数据集
        
        Args:
            workspace_id: 工作空间ID
            name: 数据集名称
            description: 描述
            embedding_model: 嵌入模型名称
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
            metadata: 元数据
            
        Returns:
            数据集信息字典
        """
        pass
    
    @abstractmethod
    async def get_dataset(
        self,
        dataset_id: UUID
    ) -> Optional[dict]:
        """
        获取数据集详情
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            数据集信息字典或None
        """
        pass
    
    @abstractmethod
    async def update_dataset(
        self,
        dataset_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        更新数据集
        
        Args:
            dataset_id: 数据集ID
            name: 数据集名称
            description: 描述
            metadata: 元数据
            
        Returns:
            更新后的数据集信息
        """
        pass
    
    @abstractmethod
    async def delete_dataset(
        self,
        dataset_id: UUID
    ) -> bool:
        """
        删除数据集
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def list_datasets(
        self,
        workspace_id: UUID,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """
        查询数据集列表
        
        Args:
            workspace_id: 工作空间ID
            keyword: 关键词搜索
            pagination: 分页参数
            
        Returns:
            分页的数据集列表
        """
        pass
    
    @abstractmethod
    async def get_dataset_statistics(
        self,
        dataset_id: UUID
    ) -> dict:
        """
        获取数据集统计信息
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            统计信息
        """
        pass
