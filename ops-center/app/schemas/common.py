from typing import Any

from pydantic import BaseModel, Field


class OperationMeta(BaseModel):
    request_id: str
    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    total_pages: int | None = None
    has_next: bool | None = None
    has_prev: bool | None = None
    data_source: str | None = None
    snapshot_at: str | None = None


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "ok"
    data: Any = Field(default_factory=dict)
    meta: OperationMeta | dict[str, Any] = Field(default_factory=dict)
