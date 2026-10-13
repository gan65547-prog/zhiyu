"""
知识库相关Schema定义

定义知识库API的请求和响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


# ============ 枚举类型 ============

class IndexingTechnique(str, Enum):
    """索引技术"""
    HIGH_QUALITY = "high_quality"
    ECONOMY = "economy"


class RetrievalMode(str, Enum):
    """检索模式"""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


# ============ 请求模型 ============

class DatasetCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    workspace_id: Optional[UUID] = Field(None, description="工作空间ID（可选，不传则使用默认工作空间）")
    indexing_technique: IndexingTechnique = Field(
        IndexingTechnique.HIGH_QUALITY,
        description="索引技术"
    )
    retrieval_mode: RetrievalMode = Field(
        RetrievalMode.HYBRID,
        description="检索模式"
    )
    embedding_model: str = Field(
        "bge-small-zh-v1.5",
        description="Embedding模型"
    )
    chunk_size: Optional[int] = Field(500, description="分块大小")
    chunk_overlap: Optional[int] = Field(50, description="分块重叠")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "企业知识库",
                "description": "公司内部文档知识库",
                "indexing_technique": "high_quality",
                "retrieval_mode": "hybrid",
                "embedding_model": "bge-small-zh-v1.5"
            }
        }


class DatasetUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    retrieval_mode: Optional[RetrievalMode] = Field(None, description="检索模式")


class DatasetQuery(BaseModel):
    """查询知识库请求"""
    workspace_id: Optional[UUID] = Field(None, description="工作空间ID")
    search: Optional[str] = Field(None, description="搜索关键词")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


# ============ 响应模型 ============

class DatasetResponse(BaseModel):
    """知识库响应"""
    id: UUID = Field(..., description="知识库ID")
    workspace_id: UUID = Field(..., description="工作空间ID")
    name: str = Field(..., description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    indexing_technique: IndexingTechnique = Field(..., description="索引技术")
    retrieval_mode: RetrievalMode = Field(..., description="检索模式")
    embedding_model: str = Field(..., description="Embedding模型")
    document_count: int = Field(0, description="文档数量")
    total_size: int = Field(0, description="总大小（字节）")
    created_by: UUID = Field(..., description="创建者ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class DatasetDetailResponse(DatasetResponse):
    """知识库详情响应"""
    settings: Dict[str, Any] = Field(default_factory=dict, description="知识库设置")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="统计信息")