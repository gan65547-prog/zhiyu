"""研究洞察 API 契约。"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ResearchQuestionInput(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    sort_order: int = Field(0, ge=0)


class ResearchSampleInput(BaseModel):
    asset_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    source_uri: Optional[str] = Field(None, max_length=4096)


class ResearchProjectCreateRequest(BaseModel):
    workspace_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=10000)
    questions: list[ResearchQuestionInput] = Field(default_factory=list)
    samples: list[ResearchSampleInput] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchConsultationRequest(BaseModel):
    workspace_id: UUID
    question: str = Field(..., min_length=1, max_length=2000)
    samples: list[ResearchSampleInput] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)


class ResearchRunCreateRequest(BaseModel):
    limits: dict[str, Any] = Field(default_factory=dict)


class ResearchReportReviewRequest(BaseModel):
    review_status: str = Field(..., pattern="^(approved|rejected)$")


class ResearchReportUpdateRequest(BaseModel):
    content_markdown: str = Field(..., min_length=1, max_length=200000)


class ResearchReportPublishRequest(BaseModel):
    dataset_id: UUID


class ResearchReportKnowledgeRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class ResearchEvidenceResponse(BaseModel):
    id: UUID
    run_id: UUID
    source_id: UUID
    quote: str
    locator: Optional[str] = None
    source_title: Optional[str] = None
    source_uri: Optional[str] = None
    created_at: datetime


class ResearchFindingResponse(BaseModel):
    id: UUID
    run_id: UUID
    claim: str
    claim_type: str
    confidence: float
    evidence_ids: list[str] = Field(default_factory=list)
    needs_review: bool
    review_status: str
    created_at: datetime


class ResearchSourceResponse(BaseModel):
    id: UUID
    run_id: UUID
    asset_id: Optional[UUID] = None
    source_uri: Optional[str] = None
    title: Optional[str] = None
    status: str
    captured_at: datetime


class ResearchEvidenceResponse(BaseModel):
    id: UUID
    run_id: UUID
    source_id: UUID
    quote: str
    locator: Optional[str] = None
    source_title: Optional[str] = None
    source_uri: Optional[str] = None
    created_at: datetime


class ResearchFindingResponse(BaseModel):
    id: UUID
    run_id: UUID
    claim: str
    claim_type: str
    confidence: float
    evidence_ids: list[str] = Field(default_factory=list)
    needs_review: bool
    review_status: str
    created_at: datetime


class ResearchProjectResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    created_by: UUID
    name: str
    description: Optional[str] = None
    status: str
    questions: list[ResearchQuestionInput] = Field(default_factory=list)
    sample_count: int = 0
    created_at: datetime
    updated_at: datetime


class ResearchProjectListResponse(BaseModel):
    items: list[ResearchProjectResponse]
    total: int
    page: int
    page_size: int


class ResearchRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    status: str
    progress: int
    current_stage: Optional[str] = None
    error_message: Optional[str] = None
    report_id: Optional[UUID] = None
    agent_run_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class ResearchRunListResponse(BaseModel):
    items: list[ResearchRunResponse]
    total: int
    page: int
    page_size: int


class ResearchReportResponse(BaseModel):
    id: UUID
    run_id: UUID
    version: int
    content_markdown: str
    content_json: dict[str, Any] = Field(default_factory=dict)
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    citation_completeness: float
    review_status: str
    published_dataset_id: Optional[UUID] = None
    published_document_id: Optional[UUID] = None
    published_knowledge_item_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
