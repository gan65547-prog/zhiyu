"""知识关系网络 API。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.knowledge_relation import KnowledgeNetworkResponse, KnowledgeRelationBatchReviewRequest, KnowledgeRelationCreateRequest, KnowledgeRelationResponse, KnowledgeRelationSuggestionResponse
from services.impl.knowledge_relation_service import KnowledgeRelationService


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.get("/network", response_model=KnowledgeNetworkResponse)
async def get_network(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        return await KnowledgeRelationService(db).network(
            tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/suggestions", response_model=list[KnowledgeRelationSuggestionResponse])
async def get_suggestions(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        return await KnowledgeRelationService(db).suggestions(
            tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/suggestions/model", response_model=list[KnowledgeRelationSuggestionResponse])
async def get_model_suggestions(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    limit: int = Query(20, ge=1, le=50),
    provider: str | None = Query(None, max_length=32),
    max_tokens: int = Query(1200, ge=128, le=4000),
):
    try:
        return await KnowledgeRelationService(db).model_suggestions(
            tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
            limit=limit, provider=provider, max_tokens=max_tokens,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=KnowledgeRelationResponse, status_code=status.HTTP_201_CREATED)
async def create_relation(request: KnowledgeRelationCreateRequest, workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await KnowledgeRelationService(db).create(
            tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), **request.model_dump(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    return result


@router.post("/suggestions/batch-review", response_model=list[KnowledgeRelationResponse], status_code=status.HTTP_201_CREATED)
async def batch_review_suggestions(
    request: KnowledgeRelationBatchReviewRequest,
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """一次确认多条候选关系；仍沿用正式关系创建时的节点、权限和审核门禁。"""
    if not request.relations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少选择一条候选关系")
    service = KnowledgeRelationService(db)
    results = []
    try:
        for relation in request.relations:
            results.append(await service.create(
                tenant_id=parse_tenant_uuid_from_user(current_user), workspace_id=workspace_id,
                user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
                **relation.model_dump(),
            ))
        await db.commit()
        return results
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relation(relation_id: UUID, workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        deleted = await KnowledgeRelationService(db).delete(
            relation_id=relation_id, workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识关系不存在")
    await db.commit()
