"""内容中心 API 契约。"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ContentTopicCreateRequest(BaseModel):
    workspace_id: UUID
    title: str = Field(min_length=1, max_length=255)
    brief: Optional[str] = Field(default=None, max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ContentTopicResponse(BaseModel):
    id: UUID; workspace_id: UUID; created_by: UUID; title: str; brief: Optional[str] = None; status: str; tags: list[str]; created_at: datetime; updated_at: datetime


class ContentTopicListResponse(BaseModel):
    items: list[ContentTopicResponse]; total: int


class ContentDraftCreateRequest(BaseModel):
    workspace_id: UUID
    topic_id: Optional[UUID] = None
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=100000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentDraftFromResearchRequest(BaseModel):
    topic_id: Optional[UUID] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)


class ContentDraftUpdateRequest(BaseModel):
    topic_id: Optional[UUID] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    body: Optional[str] = Field(default=None, max_length=100000)
    metadata: Optional[dict[str, Any]] = None


class ContentDraftRewriteRequest(BaseModel):
    platforms: list[str] = Field(min_length=1, max_length=4)
    mode: str = Field(default="deterministic", pattern="^(deterministic|model)$")
    provider: Optional[str] = Field(default=None, max_length=32)
    max_tokens: int = Field(default=1200, ge=128, le=4000)


class ContentDraftReviewRequest(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")


class ContentDraftResponse(BaseModel):
    id: UUID; workspace_id: UUID; topic_id: Optional[UUID] = None; created_by: UUID; title: str; body: str; status: str; review_status: str; reviewer_id: Optional[UUID] = None; reviewed_at: Optional[datetime] = None; metadata: dict[str, Any]; created_at: datetime; updated_at: datetime


class ContentDraftListResponse(BaseModel):
    items: list[ContentDraftResponse]; total: int


class ContentPublishRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=64)
    credential_id: Optional[UUID] = None
    external_id: Optional[str] = Field(default=None, max_length=255)
    response: dict[str, Any] = Field(default_factory=dict)


class ContentScheduleRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=64)
    credential_id: Optional[UUID] = None
    scheduled_at: datetime


class ContentPublishConfirmRequest(BaseModel):
    external_id: Optional[str] = Field(default=None, max_length=255)
    response: dict[str, Any] = Field(default_factory=dict)


class ContentConnectorResponse(BaseModel):
    key: str
    label: str
    status: str
    requires_credentials: bool = False
    supports_metric_sync: bool = False


class ContentCredentialCreateRequest(BaseModel):
    workspace_id: UUID
    platform: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    credentials: dict[str, Any] = Field(min_length=1)
    credential_hint: Optional[str] = Field(default=None, max_length=255)


class ContentCredentialResponse(BaseModel):
    id: UUID; workspace_id: UUID; platform: str; name: str; credential_hint: str; status: str; created_by: UUID; last_used_at: Optional[datetime] = None; last_error: Optional[str] = None; created_at: datetime; updated_at: datetime


class ContentCredentialTestResponse(BaseModel):
    credential_id: UUID
    platform: str
    status: str
    message: str
    connector_registered: bool
    checked_at: datetime


class XOAuthCompleteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=16, max_length=512)


class ContentMetricCreateRequest(BaseModel):
    impressions: int = Field(0, ge=0); clicks: int = Field(0, ge=0); likes: int = Field(0, ge=0); comments: int = Field(0, ge=0); shares: int = Field(0, ge=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class ContentMetricImportItem(BaseModel):
    publish_id: UUID
    collected_at: datetime
    metric: ContentMetricCreateRequest


class ContentMetricImportRequest(BaseModel):
    workspace_id: UUID
    items: list[ContentMetricImportItem] = Field(min_length=1, max_length=100)


class ContentMetricImportResponse(BaseModel):
    workspace_id: UUID
    inserted: int
    skipped: int


class ContentMetricSyncCreateRequest(BaseModel):
    workspace_id: UUID
    platform: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    credential_id: Optional[UUID] = None
    # 为空时由已注册连接器读取平台真实指标；有值时保留人工快照导入能力。
    items: list[ContentMetricImportItem] = Field(default_factory=list, max_length=100)


class ContentMetricSyncResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    platform: str
    credential_id: Optional[UUID] = None
    status: str
    inserted: int
    skipped: int
    error_message: Optional[str] = None
    task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


class ContentMetricSyncListResponse(BaseModel):
    items: list[ContentMetricSyncResponse]
    total: int


class ContentPublishResponse(BaseModel):
    id: UUID; draft_id: UUID; workspace_id: UUID; platform: str; status: str; external_id: Optional[str] = None; published_at: datetime; latest_metrics: Optional[dict[str, Any]] = None


class ContentPublishListResponse(BaseModel):
    items: list[ContentPublishResponse]
    total: int


class ContentMetricResponse(BaseModel):
    id: UUID
    publish_record_id: UUID
    workspace_id: UUID
    platform: str
    published_at: datetime
    collected_at: datetime
    impressions: int
    clicks: int
    likes: int
    comments: int
    shares: int


class ContentMetricListResponse(BaseModel):
    items: list[ContentMetricResponse]
    total: int


class ContentRetrospectiveResponse(BaseModel):
    id: UUID; publish_record_id: UUID; workspace_id: UUID; summary: str; recommendations: list[str]; metric_snapshot: dict[str, Any]; created_by: UUID; created_at: datetime
