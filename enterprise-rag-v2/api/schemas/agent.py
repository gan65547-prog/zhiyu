"""Agent Runtime API contracts."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentDefinitionCreateRequest(BaseModel):
    workspace_id: UUID
    name: str
    agent_type: str
    description: Optional[str] = None
    workflow: list[dict[str, Any]] = Field(default_factory=list)


class AgentDefinitionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    agent_type: str
    description: Optional[str] = None
    version: int
    workflow: list[dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime


class AgentRunStepResponse(BaseModel):
    id: UUID
    step_key: str
    step_order: int
    status: str
    output_json: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class AgentRunResponse(BaseModel):
    id: UUID
    research_run_id: Optional[UUID] = None
    definition_id: UUID
    status: str
    current_step: Optional[str] = None
    progress: int
    error_message: Optional[str] = None
    retry_count: int
    steps: list[AgentRunStepResponse]
    created_at: datetime
    updated_at: datetime


class AgentRunListResponse(BaseModel):
    items: list[AgentRunResponse]
    total: int
    page: int
    page_size: int


class AgentRunCreateRequest(BaseModel):
    workspace_id: UUID
    definition_id: UUID
    input: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentToolExecutionRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class AgentToolExecutionResponse(BaseModel):
    run_id: UUID
    step_key: str
    tool: str
    status: str
    approval_id: Optional[UUID] = None
    output: dict[str, Any] = Field(default_factory=dict)


class AgentScheduleCreateRequest(BaseModel):
    workspace_id: UUID
    definition_id: UUID
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    schedule_expression: str = Field(min_length=9, max_length=128)
    timezone: str = "Asia/Shanghai"
    next_run_at: datetime
    config_json: dict[str, Any] = Field(default_factory=dict)


class AgentScheduleResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    definition_id: UUID
    project_id: UUID
    name: str
    schedule_expression: str
    timezone: str
    config_json: dict[str, Any]
    enabled: bool
    next_run_at: datetime
    last_run_at: Optional[datetime] = None
    last_run_id: Optional[UUID] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AgentApprovalResponse(BaseModel):
    id: UUID
    agent_run_id: UUID
    research_run_id: Optional[UUID] = None
    step_id: Optional[UUID] = None
    step_key: Optional[str] = None
    status: str
    reviewer_id: Optional[UUID] = None
    comment: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class AgentApprovalReviewRequest(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    comment: Optional[str] = Field(default=None, max_length=2000)


class AgentToolResponse(BaseModel):
    key: str
    label: str
    description: str
    input_schema: dict[str, Any]
    requires_approval: bool
    read_only: bool




class AgentEventResponse(BaseModel):
    id: UUID
    event_type: str
    step_key: Optional[str] = None
    status: str
    title: Optional[str] = None
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
