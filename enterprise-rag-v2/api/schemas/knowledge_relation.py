"""知识关系网络 API 契约。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class KnowledgeRelationCreateRequest(BaseModel):
    source_item_id: UUID
    target_item_id: UUID
    relation_type: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("relation_type")
    @classmethod
    def normalize_relation_type(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("关系类型不能为空")
        return value


class KnowledgeRelationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    source_item_id: UUID
    target_item_id: UUID
    source_title: str
    target_title: str
    relation_type: str
    description: str | None = None
    created_by: UUID | None = None
    created_at: datetime


class KnowledgeNetworkResponse(BaseModel):
    nodes: list[dict]
    edges: list[KnowledgeRelationResponse]


class KnowledgeRelationSuggestionResponse(BaseModel):
    source_item_id: UUID
    target_item_id: UUID
    source_title: str
    target_title: str
    relation_type: str
    score: float
    matched_terms: list[str]
    requires_human_review: bool
    description: str = ""
    origin: str = "rules"


class KnowledgeRelationBatchReviewRequest(BaseModel):
    relations: list[KnowledgeRelationCreateRequest] = Field(default_factory=list, max_length=100)
