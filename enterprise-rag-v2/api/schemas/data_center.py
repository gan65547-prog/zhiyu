"""数据中心只读聚合查询契约。"""

from typing import Any

from pydantic import BaseModel, Field


class DataCenterSection(BaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)


class DataCenterContentPerformance(BaseModel):
    publish_count: int = 0
    impressions: int = 0
    clicks: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    click_through_rate: float = 0.0


class DataCenterResponse(BaseModel):
    workspace_id: str
    assets: DataCenterSection
    knowledge: DataCenterSection
    research: DataCenterSection
    agents: DataCenterSection
    content_drafts: DataCenterSection
    content_performance: DataCenterContentPerformance
    health: dict[str, Any] = Field(default_factory=dict)
