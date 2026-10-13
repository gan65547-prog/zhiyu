"""AI 工作台聚合查询契约。"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WorkbenchSearchItem(BaseModel):
    id: UUID
    kind: str
    title: str
    snippet: str = ""
    route: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkbenchSearchResponse(BaseModel):
    items: list[WorkbenchSearchItem]
    total: int
    query: str


class WorkbenchTask(BaseModel):
    id: UUID
    kind: str
    title: str
    status: str
    priority: int
    route: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkbenchTaskListResponse(BaseModel):
    items: list[WorkbenchTask]
    total: int
