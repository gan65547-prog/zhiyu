"""
文档服务接口

定义文档管理相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from uuid import UUID
from core.value_objects.pagination import Pagination, Page


class DocumentService(ABC):
    """文档服务抽象接口"""
    
    @abstractmethod
    async def upload_document(
        self,
        dataset_id: UUID,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        knowledge_type: Optional[str] = None,
    ) -> dict:
        """
        上传文档

        Args:
            dataset_id: 数据集ID
            file_path: 文件路径
            file_name: 文件名
            file_type: 文件类型
            file_size: 文件大小
            tags: 标签列表
            metadata: 元数据
            knowledge_type: 知识分层类型

        Returns:
            文档信息字典
        """
        pass

    @abstractmethod
    async def get_document(
        self,
        document_id: UUID
    ) -> Optional[dict]:
        """
        获取文档详情

        Args:
            document_id: 文档ID

        Returns:
            文档信息字典或None
        """
        pass

    @abstractmethod
    async def update_document(
        self,
        document_id: UUID,
        file_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        knowledge_type: Optional[str] = None,
    ) -> dict:
        """
        更新文档

        Args:
            document_id: 文档ID
            file_name: 文件名
            tags: 标签列表
            metadata: 元数据
            knowledge_type: 知识分层类型

        Returns:
            更新后的文档信息
        """
        pass

    @abstractmethod
    async def delete_document(
        self,
        document_id: UUID
    ) -> bool:
        """
        删除文档

        Args:
            document_id: 文档ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def batch_delete_documents(
        self,
        document_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        批量删除文档

        Args:
            document_ids: 文档ID列表

        Returns:
            删除结果统计
        """
        pass

    @abstractmethod
    async def list_documents(
        self,
        dataset_id: Optional[UUID] = None,
        status: Optional[str] = None,
        file_type: Optional[str] = None,
        knowledge_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """
        查询文档列表

        Args:
            dataset_id: 数据集ID
            status: 文档状态
            file_type: 文件类型
            knowledge_type: 知识分层类型
            tags: 标签列表
            keyword: 关键词搜索
            pagination: 分页参数

        Returns:
            分页的文档列表
        """
        pass
    
    @abstractmethod
    async def reindex_document(
        self,
        document_id: UUID,
        force: bool = False
    ) -> dict:
        """
        重新索引文档
        
        Args:
            document_id: 文档ID
            force: 是否强制重新索引
            
        Returns:
            任务信息
        """
        pass
    
    @abstractmethod
    async def get_document_statistics(
        self,
        dataset_id: Optional[UUID] = None
    ) -> dict:
        """
        获取文档统计信息
        
        Args:
            dataset_id: 数据集ID（可选）
            
        Returns:
            统计信息
        """
        pass

    @abstractmethod
    async def get_dataset_document_counts(
        self,
        dataset_id: UUID
    ) -> dict:
        """
        按处理状态统计数据集文档数量（问答就绪度用）

        Args:
            dataset_id: 数据集ID

        Returns:
            {"completed": int, "processing": int, "failed": int}
        """
        pass

    @abstractmethod
    async def get_document_original_text(
        self,
        document_id: UUID
    ) -> str:
        """
        获取文档原始文本（从上传文件直接提取，不走分段拼接）

        Args:
            document_id: 文档ID

        Returns:
            文本内容
        """
        pass
    
    @abstractmethod
    async def process_document(
        self,
        document_id: UUID
    ) -> bool:
        """
        处理文档（提取文本、分块、向量化）
        
        Args:
            document_id: 文档ID
            
        Returns:
            是否成功
        """
        pass
