"""
Document API Schemas
文档管理相关的请求和响应模型
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from .base import BaseResponse, PaginatedResponse


class DocumentStatus(str, Enum):
    """文档状态枚举"""
    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class DocumentType(str, Enum):
    """文档格式类型枚举"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    EPUB = "epub"
    IMAGE = "image"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"


class KnowledgeType(str, Enum):
    """知识分层类型枚举"""
    TOPIC = "topic"           # 领域全景，导航性质
    CONCEPT = "concept"       # 深度概念，需要完整保留上下文
    SUMMARY = "summary"       # 项目复盘/学习路径
    RECIPE = "recipe"         # 操作手册/检查清单，步骤性
    REFERENCE = "reference"   # API 参考/原始文档
    ERRATA = "errata"         # 勘误/已知问题


# =----------- Request Models =-----------

class DocumentUploadToDatasetRequest(BaseModel):
    """上传文档到指定数据集的请求"""
    file_name: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    tags: Optional[List[str]] = Field(default=None, description="标签列表")
    metadata: Optional[dict] = Field(default=None, description="元数据")


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""
    dataset_id: str = Field(..., description="数据集ID")
    file_name: str = Field(..., description="文件名")
    file_type: DocumentType = Field(..., description="文件类型")
    tags: Optional[List[str]] = Field(default=None, description="标签列表")
    metadata: Optional[dict] = Field(default=None, description="元数据")


class DocumentUpdateRequest(BaseModel):
    """文档更新请求"""
    file_name: Optional[str] = Field(None, description="文件名")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[dict] = Field(None, description="元数据")
    knowledge_type: Optional[KnowledgeType] = Field(None, description="知识分层类型")


class DocumentQueryRequest(BaseModel):
    """文档查询请求"""
    dataset_id: Optional[str] = Field(None, description="数据集ID")
    status: Optional[DocumentStatus] = Field(None, description="文档状态")
    file_type: Optional[DocumentType] = Field(None, description="文件类型")
    knowledge_type: Optional[KnowledgeType] = Field(None, description="知识分层类型")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class DocumentBatchDeleteRequest(BaseModel):
    """文档批量删除请求"""
    document_ids: List[str] = Field(..., min_items=1, description="文档ID列表")


class DocumentReindexRequest(BaseModel):
    """文档重新索引请求"""
    document_id: str = Field(..., description="文档ID")
    force: bool = Field(False, description="是否强制重新索引")


# ============ Response Models ============

class DocumentInfo(BaseModel):
    """文档信息"""
    id: str = Field(..., description="文档ID")
    dataset_id: str = Field(..., description="数据集ID")
    file_name: str = Field(..., description="文件名")
    file_type: DocumentType = Field(..., description="文件格式类型")
    file_size: int = Field(..., description="文件大小(字节)")
    status: DocumentStatus = Field(..., description="文档状态")
    knowledge_type: Optional[KnowledgeType] = Field(None, description="知识分层类型")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    metadata: dict = Field(default_factory=dict, description="元数据")
    chunk_count: int = Field(0, description="分块数量")
    indexed_at: Optional[datetime] = Field(None, description="索引时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class DocumentUploadResponse(BaseResponse):
    """文档上传响应"""
    data: DocumentInfo


class DocumentDetailResponse(BaseResponse):
    """文档详情响应"""
    data: DocumentInfo


class DocumentListResponse(PaginatedResponse):
    """文档列表响应"""
    data: List[DocumentInfo]


class DocumentDeleteResponse(BaseResponse):
    """文档删除响应"""
    data: dict = Field(default_factory=lambda: {"deleted": True})


class DocumentBatchDeleteResponse(BaseResponse):
    """文档批量删除响应"""
    data: dict  # {"deleted_count": int, "failed_ids": List[str]}


class DocumentReindexResponse(BaseResponse):
    """文档重新索引响应"""
    data: dict  # {"task_id": str, "status": str}


# ============ Statistics Models ============

class DocumentStatistics(BaseModel):
    """文档统计信息"""
    total_count: int = Field(..., description="总文档数")
    pending_count: int = Field(..., description="待处理数")
    processing_count: int = Field(..., description="处理中数")
    completed_count: int = Field(..., description="已完成数")
    failed_count: int = Field(..., description="失败数")
    total_size: int = Field(..., description="总大小(字节)")
    total_chunks: int = Field(..., description="总分块数")


class DocumentStatisticsResponse(BaseResponse):
    """文档统计响应"""
    data: DocumentStatistics
