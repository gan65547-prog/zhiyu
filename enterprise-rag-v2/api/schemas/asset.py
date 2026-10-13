"""AI 工作台素材 API schemas。"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AssetCreateRequest(BaseModel):
    workspace_id: UUID
    dataset_id: Optional[UUID] = None
    source_type: str = Field(..., pattern="^(file|url|text|chat)$")
    title: str = Field(..., min_length=1, max_length=255)
    source_uri: Optional[str] = Field(None, max_length=4096)
    mime_type: Optional[str] = Field(None, max_length=127)
    size_bytes: int = Field(0, ge=0)
    content_hash: Optional[str] = Field(None, min_length=64, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetImportUrlRequest(BaseModel):
    workspace_id: UUID
    dataset_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=255)
    source_uri: str = Field(..., min_length=1, max_length=4096)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetImportUrlBatchRequest(BaseModel):
    workspace_id: UUID
    dataset_id: Optional[UUID] = None
    urls: list[str] = Field(..., min_length=1, max_length=50)


class KnowledgePackageClaim(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class KnowledgePackageImportRequest(BaseModel):
    """外部授权知识包的最小导入契约。

    缺少治理字段时仍允许进入素材中心，但只能标记为 unverified，不能直接
    作为正式知识、研究结论或对外内容的依据。
    """

    workspace_id: UUID
    dataset_id: Optional[UUID] = None
    package_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    title: str = Field(..., min_length=1, max_length=255)
    source_system: str = Field(..., min_length=1, max_length=128)
    source_version: Optional[str] = Field(None, max_length=128)
    provided_by: Optional[str] = Field(None, max_length=255)
    licensed_scope: Optional[str] = Field(None, max_length=255)
    tested_at: Optional[datetime] = None
    claims: list[KnowledgePackageClaim] = Field(default_factory=list, max_length=200)
    limits: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("title", "source_system", "provided_by", "licensed_scope")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value

    @field_validator("limits")
    @classmethod
    def normalize_limits(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def governance_issues(self) -> list[str]:
        issues: list[str] = []
        if not self.source_version:
            issues.append("缺少 source_version")
        if not self.provided_by:
            issues.append("缺少 provided_by")
        if not self.licensed_scope:
            issues.append("缺少 licensed_scope")
        if not self.tested_at:
            issues.append("缺少 tested_at")
        if not self.claims:
            issues.append("至少需要一条 claims")
        if any(not claim.evidence_refs for claim in self.claims):
            issues.append("每条 claim 必须包含 evidence_refs")
        if not self.limits:
            issues.append("至少需要一条 limits")
        return issues

    def as_asset_metadata(self) -> dict[str, Any]:
        issues = self.governance_issues()
        return {
            "knowledge_package": self.model_dump(mode="json", exclude={"workspace_id", "dataset_id"}),
            "governance": {
                "verification_status": "verified" if not issues else "unverified",
                "issues": issues,
                "can_seed_formal_knowledge": not issues,
            },
        }


class AssetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    dataset_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    created_by: UUID
    legacy_document_id: Optional[UUID] = None
    source_type: str
    title: str
    source_uri: Optional[str] = None
    storage_key: Optional[str] = None
    source_etag: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: int
    content_hash: Optional[str] = None
    status: str
    processing_error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int


class AssetIngestionResponse(BaseModel):
    asset_id: UUID
    status: str
    task_id: Optional[str] = None


class AssetTextIngestionRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2_000_000)


class AssetProcessingStatusResponse(BaseModel):
    asset_id: UUID
    status: str
    progress: int = 0
    phase: Optional[str] = None
    document_id: Optional[UUID] = None
    document_status: Optional[str] = None
    done_chunks: int = 0
    total_chunks: int = 0
    stalled: bool = False
    processing_error: Optional[str] = None


class AssetBatchResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    assets: list[AssetResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AssetOrganizeResponse(BaseModel):
    asset_id: UUID
    agent_run_id: UUID
    status: str
    task_id: Optional[str] = None
