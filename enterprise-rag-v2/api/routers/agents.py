"""显式 Agent Runtime 查询与取消 API。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.agent import AgentApprovalResponse, AgentApprovalReviewRequest, AgentDefinitionCreateRequest, AgentDefinitionResponse, AgentEventResponse, AgentRunCreateRequest, AgentRunListResponse, AgentRunResponse, AgentScheduleCreateRequest, AgentScheduleResponse, AgentToolExecutionRequest, AgentToolExecutionResponse, AgentToolResponse
from services.impl.agent_runtime_service import AgentRuntimeService
from infrastructure.queue.research_tasks import run_research_task


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.get("/approvals", response_model=list[AgentApprovalResponse])
async def list_agent_approvals(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db), pending_only: bool = Query(True)):
    try:
        return await AgentRuntimeService(db).list_approvals(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), pending_only=pending_only)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/tools", response_model=list[AgentToolResponse])
async def list_agent_tools(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    return AgentRuntimeService(db).list_tools()


@router.post("/approvals/{approval_id}/review", response_model=AgentApprovalResponse)
async def review_agent_approval(approval_id: UUID, request: AgentApprovalReviewRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await AgentRuntimeService(db).review_approval(approval_id=approval_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), status=request.status, comment=request.comment)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审批不存在")
    await db.commit()
    return result


@router.get("/schedules", response_model=list[AgentScheduleResponse])
async def list_agent_schedules(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        return await AgentRuntimeService(db).list_schedules(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/schedules", response_model=AgentScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_schedule(request: AgentScheduleCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await AgentRuntimeService(db).create_schedule(tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump())
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/schedules/{schedule_id}/enable", response_model=AgentScheduleResponse)
async def enable_agent_schedule(schedule_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await AgentRuntimeService(db).set_schedule_enabled(schedule_id=schedule_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), enabled=True)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调度不存在")
    await db.commit()
    return result


@router.post("/schedules/{schedule_id}/disable", response_model=AgentScheduleResponse)
async def disable_agent_schedule(schedule_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await AgentRuntimeService(db).set_schedule_enabled(schedule_id=schedule_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), enabled=False)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调度不存在")
    await db.commit()
    return result


@router.get("", response_model=list[AgentDefinitionResponse])
async def list_agent_definitions(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        return await AgentRuntimeService(db).list_definitions(
            workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("", response_model=AgentDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_definition(
    request: AgentDefinitionCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AgentRuntimeService(db).create_definition(
            tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump(),
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/runs/{agent_run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    agent_run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AgentRuntimeService(db).get_run(
            agent_run_id=agent_run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 运行不存在")
    return result


@router.post("/runs", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_agent_run(request: AgentRunCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await AgentRuntimeService(db).create_run(
            tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump(),
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/runs/{agent_run_id}/steps/{step_key}/execute", response_model=AgentToolExecutionResponse)
async def execute_agent_tool_step(agent_run_id: UUID, step_key: str, request: AgentToolExecutionRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await AgentRuntimeService(db).execute_tool_step(
            agent_run_id=agent_run_id, step_key=step_key, arguments=request.input,
            tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 运行不存在")
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/runs/{agent_run_id}/events", response_model=list[AgentEventResponse])
async def list_agent_events(
    agent_run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AgentRuntimeService(db).list_events(
            agent_run_id=agent_run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 运行不存在")
    return result


@router.get("/runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    try:
        return await AgentRuntimeService(db).list_runs(
            workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), page=page, page_size=page_size,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/runs/{agent_run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    agent_run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AgentRuntimeService(db).cancel_run(
            agent_run_id=agent_run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 运行不存在")
    await db.commit()
    return result


@router.post("/runs/{agent_run_id}/retry", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_agent_run(
    agent_run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    tenant_id = parse_tenant_uuid_from_user(current_user)
    try:
        result = await AgentRuntimeService(db).retry_run(
            agent_run_id=agent_run_id, tenant_id=tenant_id, user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 运行不存在")
        await db.commit()
        if result.get("research_run_id"):
            task = run_research_task.delay(str(result["research_run_id"]), str(tenant_id))
            result["task_id"] = task.id
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
