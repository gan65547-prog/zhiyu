"""
Errata API Schemas
勘误管理相关的请求和响应模型
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from api.schemas.document import KnowledgeType


class ErrataSeverity(str):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NOTE = "note"


class ErrataStatus(str):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ============ Request Models ============

class ErrataCreateRequest(BaseModel):
    """创建勘误请求"""
    errata_code: str = Field(..., description="勘误编号 (E-001)")
    title: str = Field(..., min_length=1, max_length=255, description="勘误标题")
    description: str = Field(..., min_length=1, description="问题描述")
    severity: str = Field("minor", description="严重程度: critical/major/minor/note")
    fix_suggestion: Optional[str] = Field(None, description="修正建议")
    source_evidence: Optional[str] = Field(None, description="来源证据")
    affected_document_ids: List[str] = Field(default_factory=list, description="受影响的文档ID列表")
    related_document_ids: List[str] = Field(default_factory=list, description="关联文档ID列表")
    reported_by: Optional[str] = Field(None, description="报告人")


class ErrataUpdateRequest(BaseModel):
    """更新勘误请求"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    fix_suggestion: Optional[str] = None
    source_evidence: Optional[str] = None
    affected_document_ids: Optional[List[str]] = None
    related_document_ids: Optional[List[str]] = None
    reported_by: Optional[str] = None


class ErrataQueryRequest(BaseModel):
    """勘误查询请求"""
    severity: Optional[str] = Field(None, description="按严重程度过滤")
    status: Optional[str] = Field(None, description="按状态过滤")
    document_id: Optional[str] = Field(None, description="关联文档ID")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ============ Response Models ============

class ErrataInfo(BaseModel):
    """勘误信息"""
    id: str
    errata_code: str
    title: str
    description: str
    severity: str
    status: str
    fix_suggestion: Optional[str] = None
    source_evidence: Optional[str] = None
    affected_document_ids: List[str] = Field(default_factory=list)
    related_document_ids: List[str] = Field(default_factory=list)
    reported_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DocumentErrataResponse(BaseModel):
    """文档关联勘误响应 — 用于 RAG 检索结果中标记勘误"""
    document_id: str
    document_name: str
    errata_list: List[ErrataInfo]
    total_count: int
