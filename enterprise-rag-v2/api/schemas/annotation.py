from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DocumentAnnotationCreateRequest(BaseModel):
    kind: Literal["note", "understanding"] = "note"
    quote: str = Field(default="", max_length=5000)
    body: str = Field(..., min_length=1, max_length=20000)
    question: Optional[str] = Field(default=None, max_length=5000)


class DocumentAnnotationResponse(BaseModel):
    id: str
    document_id: str
    author_id: str
    kind: str
    quote: str
    body: str
    question: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentAnnotationListResponse(BaseModel):
    items: list[DocumentAnnotationResponse]
    total: int
