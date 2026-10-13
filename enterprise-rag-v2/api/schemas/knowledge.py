"""知识中心 API 契约。"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeItemCreateRequest(BaseModel):
    workspace_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    item_type: str = Field("concept", min_length=1, max_length=32)
    definition: str = Field("", max_length=20000)
    details: Optional[str] = Field(None, max_length=100000)
    conclusions: list[str] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeItemUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    item_type: Optional[str] = Field(None, min_length=1, max_length=32)
    definition: Optional[str] = Field(None, max_length=20000)
    details: Optional[str] = Field(None, max_length=100000)
    conclusions: Optional[list[str]] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)


class KnowledgeReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|draft)$")


class KnowledgeEvidenceCreateRequest(BaseModel):
    asset_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    chunk_id: Optional[UUID] = None
    research_evidence_id: Optional[UUID] = None
    quote: str = Field(..., min_length=1, max_length=20000)
    locator: Optional[str] = Field(None, max_length=255)
    source_uri: Optional[str] = Field(None, max_length=4096)


class KnowledgeEvidenceResponse(BaseModel):
    id: UUID
    knowledge_item_id: UUID
    asset_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    chunk_id: Optional[UUID] = None
    research_evidence_id: Optional[UUID] = None
    quote: str
    locator: Optional[str] = None
    source_uri: Optional[str] = None
    created_by: UUID
    created_at: datetime


class KnowledgeItemResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    created_by: UUID
    title: str
    item_type: str
    definition: str
    details: Optional[str] = None
    conclusions: list[str] = Field(default_factory=list)
    confidence: float
    review_status: str
    reviewer_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    evidence: list[KnowledgeEvidenceResponse] = Field(default_factory=list)


class KnowledgeItemListResponse(BaseModel):
    items: list[KnowledgeItemResponse]
    total: int
    page: int
    page_size: int


class KnowledgeItemVersionResponse(BaseModel):
    id: UUID
    knowledge_item_id: UUID
    version: int
    title: str
    item_type: str
    definition: str
    details: Optional[str] = None
    conclusions: list[str] = Field(default_factory=list)
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: UUID
    created_at: datetime
