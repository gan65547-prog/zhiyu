"""AI 工作台知识中心 API。"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.knowledge import (
    KnowledgeEvidenceCreateRequest,
    KnowledgeEvidenceResponse,
    KnowledgeItemCreateRequest,
    KnowledgeItemListResponse,
    KnowledgeItemResponse,
    KnowledgeItemUpdateRequest,
    KnowledgeReviewRequest,
    KnowledgeItemVersionResponse,
)
from services.impl.knowledge_service import KnowledgeService


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


def _service(db) -> KnowledgeService:
    return KnowledgeService(db)


@router.post("", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_item(
    request: KnowledgeItemCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        return await _service(db).create_item(
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
            **request.model_dump(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("", response_model=KnowledgeItemListResponse)
async def list_knowledge_items(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    review_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        return await _service(db).list_items(
            tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
            user_id=_user_id(current_user), page=page, page_size=page_size,
            review_status=review_status, is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/{item_id}", response_model=KnowledgeItemResponse)
async def get_knowledge_item(
    item_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await _service(db).get_item(
            item_id=item_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识卡片不存在")
    return result


@router.patch("/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    item_id: UUID,
    request: KnowledgeItemUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await _service(db).update_item(
            item_id=item_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
            changes=request.model_dump(exclude_unset=True),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识卡片不存在")
    return result


@router.post("/{item_id}/review", response_model=KnowledgeItemResponse)
async def review_knowledge_item(
    item_id: UUID,
    request: KnowledgeReviewRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await _service(db).review_item(
            item_id=item_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
            review_status=request.status,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识卡片不存在")
    return result


@router.get("/{item_id}/versions", response_model=list[KnowledgeItemVersionResponse])
async def list_knowledge_versions(
    item_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await _service(db).list_versions(
            item_id=item_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识卡片不存在")
    return result


@router.post("/{item_id}/versions/{version_id}/rollback", response_model=KnowledgeItemResponse)
async def rollback_knowledge_version(
    item_id: UUID,
    version_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await _service(db).rollback_item(
            item_id=item_id, version_id=version_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识卡片不存在")
    return result


@router.post("/{item_id}/evidence", response_model=KnowledgeEvidenceResponse, status_code=status.HTTP_201_CREATED)
async def add_knowledge_evidence(
    item_id: UUID,
    request: KnowledgeEvidenceCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await _service(db).add_evidence(
            item_id=item_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
            **request.model_dump(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识卡片不存在")
    return result
