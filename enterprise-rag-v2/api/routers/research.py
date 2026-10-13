"""行业知识咨询与研究项目 API。"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_active_user, get_db, get_quota_service, parse_tenant_uuid_from_user
from api.schemas.research import (
    ResearchProjectCreateRequest,
    ResearchProjectListResponse,
    ResearchProjectResponse,
    ResearchRunCreateRequest,
    ResearchRunListResponse,
    ResearchRunResponse,
    ResearchReportResponse,
    ResearchReportReviewRequest,
    ResearchReportUpdateRequest,
    ResearchReportPublishRequest,
    ResearchConsultationRequest,
    ResearchReportKnowledgeRequest,
    ResearchEvidenceResponse,
    ResearchFindingResponse,
)
from infrastructure.queue.research_tasks import run_research_task
from infrastructure.queue.asset_tasks import process_asset_document_task
from services.impl.research_service import ResearchService


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.post("/consultations", response_model=ResearchRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_consultation(
    request: ResearchConsultationRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    quota_service=Depends(get_quota_service),
):
    service = ResearchService(db, quota_service=quota_service)
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    try:
        project = await service.create_project(
            tenant_id=tenant_id, user_id=user_id, is_superuser=bool(current_user.get("is_superuser")),
            data={
                "workspace_id": request.workspace_id, "name": f"即时咨询-{request.question[:32]}",
                "description": "由即时咨询自动创建的临时研究项目", "questions": [{"question": request.question, "sort_order": 0}],
                "samples": [sample.model_dump() for sample in request.samples], "metadata": {**request.metadata, "consultation": True},
            },
        )
        result = await service.create_run(
            project_id=UUID(str(project["id"])), tenant_id=tenant_id, user_id=user_id,
            is_superuser=bool(current_user.get("is_superuser")), limits=request.limits,
        )
        await db.commit()
        task = run_research_task.delay(str(result["id"]), str(tenant_id))
        result["task_id"] = task.id
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects", response_model=ResearchProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ResearchProjectCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        return await ResearchService(db).create_project(
            tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/projects", response_model=ResearchProjectListResponse)
async def list_projects(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    try:
        return await ResearchService(db).list_projects(
            tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
            user_id=_user_id(current_user), page=page, page_size=page_size,
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/projects/{project_id}/runs", response_model=ResearchRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    project_id: UUID,
    request: ResearchRunCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    quota_service=Depends(get_quota_service),
):
    try:
        result = await ResearchService(db, quota_service=quota_service).create_run(
            project_id=project_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), limits=request.limits,
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项目不存在")
        await db.commit()
        task = run_research_task.delay(str(result["id"]), str(parse_tenant_uuid_from_user(current_user)))
        result["task_id"] = task.id
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/projects/{project_id}/runs", response_model=ResearchRunListResponse)
async def list_runs(
    project_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    try:
        result = await ResearchService(db).list_runs(
            project_id=project_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            page=page, page_size=page_size, is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项目不存在")
    return result


@router.get("/runs/{run_id}", response_model=ResearchRunResponse)
async def get_run(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).get_run(
            run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究运行不存在")
    return result


@router.post("/runs/{run_id}/cancel", response_model=ResearchRunResponse)
async def cancel_run(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).cancel_run(
            run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究运行不存在")
    return result


@router.post("/runs/{run_id}/retry", response_model=ResearchRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_run(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    tenant_id = parse_tenant_uuid_from_user(current_user)
    try:
        result = await ResearchService(db).retry_run(
            run_id=run_id, tenant_id=tenant_id, user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究运行不存在")
        await db.commit()
        task = run_research_task.delay(str(run_id), str(tenant_id))
        result["task_id"] = task.id
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/runs/{run_id}/report", response_model=ResearchReportResponse)
async def get_report(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).get_report(
            run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究报告不存在")
    return result


@router.get("/projects/{project_id}/evidence", response_model=list[ResearchEvidenceResponse])
async def list_project_evidence(
    project_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """返回项目最近一次运行的证据；运行级查询仍是唯一数据边界。"""
    try:
        runs = await ResearchService(db).list_runs(
            project_id=project_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            page=1, page_size=1, is_superuser=bool(current_user.get("is_superuser")),
        )
        if runs is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项目不存在")
        if not runs["items"]:
            return []
        result = await ResearchService(db).list_evidence(
            run_id=UUID(str(runs["items"][0]["id"])), tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
        return result or []
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/projects/{project_id}/findings", response_model=list[ResearchFindingResponse])
async def list_project_findings(
    project_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        runs = await ResearchService(db).list_runs(
            project_id=project_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            page=1, page_size=1, is_superuser=bool(current_user.get("is_superuser")),
        )
        if runs is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项目不存在")
        if not runs["items"]:
            return []
        result = await ResearchService(db).list_findings(
            run_id=UUID(str(runs["items"][0]["id"])), tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
        return result or []
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/runs/{run_id}/evidence", response_model=list[ResearchEvidenceResponse])
async def list_run_evidence(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).list_evidence(
            run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究运行不存在")
    return result


@router.get("/runs/{run_id}/findings", response_model=list[ResearchFindingResponse])
async def list_run_findings(
    run_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).list_findings(
            run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究运行不存在")
    return result


@router.post("/reports/{report_id}/review", response_model=ResearchReportResponse)
async def review_report(
    report_id: UUID,
    request: ResearchReportReviewRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).review_report(
            report_id=report_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), review_status=request.review_status,
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究报告不存在")
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/reports/{report_id}", response_model=ResearchReportResponse)
async def update_report(
    report_id: UUID,
    request: ResearchReportUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).update_report(
            report_id=report_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), content_markdown=request.content_markdown,
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究报告不存在")
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/reports/{report_id}/publish-to-dataset", response_model=ResearchReportResponse)
async def publish_report(
    report_id: UUID,
    request: ResearchReportPublishRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).publish_report(
            report_id=report_id, dataset_id=request.dataset_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究报告不存在")
        await db.commit()
        if result.get("published_asset_id") and result.get("published_document_id"):
            process_asset_document_task.apply_async(
                args=[result["published_asset_id"], result["published_document_id"], str(parse_tenant_uuid_from_user(current_user))],
                queue="documents_high",
            )
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/reports/{report_id}/publish-to-knowledge", response_model=ResearchReportResponse)
async def publish_report_to_knowledge(
    report_id: UUID,
    request: ResearchReportKnowledgeRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await ResearchService(db).publish_report_to_knowledge(
            report_id=report_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), title=request.title,
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究报告不存在")
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
