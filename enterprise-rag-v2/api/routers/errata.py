"""
勘误管理 API Router

提供文档勘误的 CRUD 操作和关联查询
GET /api/v1/errata/               — 列表查询
POST /api/v1/errata/              — 创建勘误
GET /api/v1/errata/{id}          — 获取勘误
PUT /api/v1/errata/{id}          — 更新勘误
DELETE /api/v1/errata/{id}       — 删除勘误
GET /api/v1/documents/{id}/errata — 获取文档关联的勘误
"""

from typing import Annotated, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas.base import DataResponse, PaginatedResponse
from api.schemas.errata import (
    ErrataCreateRequest,
    ErrataUpdateRequest,
    ErrataQueryRequest,
    ErrataInfo,
    DocumentErrataResponse,
)
from services.impl.errata_service import ErrataService, get_errata_service
from api.deps import get_current_active_user
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

errata_router = APIRouter(prefix="/api/v1/errata", tags=["Errata"])


def _errata_to_dict(e) -> dict:
    """将 ORM 对象转为响应字典"""
    return {
        "id": str(e.id),
        "errata_code": e.errata_code,
        "title": e.title,
        "description": e.description,
        "severity": e.severity.value if hasattr(e.severity, 'value') else e.severity,
        "status": e.status.value if hasattr(e.status, 'value') else e.status,
        "fix_suggestion": e.fix_suggestion,
        "source_evidence": e.source_evidence,
        "affected_document_ids": list(e.affected_document_ids or []),
        "related_document_ids": list(e.related_document_ids or []),
        "reported_by": e.reported_by,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@errata_router.post("/")
async def create_errata(
    request: ErrataCreateRequest,
    errata_service: Annotated[ErrataService, Depends(get_errata_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)] = None,
):
    """创建勘误"""
    try:
        result = await errata_service.create_errata(
            errata_code=request.errata_code,
            title=request.title,
            description=request.description,
            severity=request.severity,
            fix_suggestion=request.fix_suggestion,
            source_evidence=request.source_evidence,
            affected_document_ids=request.affected_document_ids,
            related_document_ids=request.related_document_ids,
            reported_by=request.reported_by,
        )
        return {"success": True, "data": _errata_to_dict(result)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create errata: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create errata",
        )


@errata_router.get("/")
async def list_errata(
    errata_service: Annotated[ErrataService, Depends(get_errata_service)],
    severity: str = None,
    status_filter: str = Query(None, alias="status"),
    document_id: UUID = None,
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询勘误列表"""
    result = await errata_service.list_errata(
        severity=severity,
        status_filter=status_filter,
        document_id=str(document_id) if document_id else None,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "data": {
            "items": [_errata_to_dict(e) for e in result["items"]],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
        },
    }


@errata_router.get("/{errata_id}")
async def get_errata(
    errata_id: UUID,
    errata_service: Annotated[ErrataService, Depends(get_errata_service)],
):
    """获取勘误详情"""
    e = await errata_service.get_errata(errata_id)
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Errata not found")
    return {"success": True, "data": _errata_to_dict(e)}


@errata_router.put("/{errata_id}")
async def update_errata(
    errata_id: UUID,
    request: ErrataUpdateRequest,
    errata_service: Annotated[ErrataService, Depends(get_errata_service)],
):
    """更新勘误"""
    try:
        result = await errata_service.update_errata(
            errata_id=errata_id,
            **request.model_dump(exclude_unset=True),
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Errata not found")
        return {"success": True, "data": _errata_to_dict(result)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update errata: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update errata",
        )


@errata_router.delete("/{errata_id}")
async def delete_errata(
    errata_id: UUID,
    errata_service: Annotated[ErrataService, Depends(get_errata_service)],
):
    """删除勘误"""
    try:
        ok = await errata_service.delete_errata(errata_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Errata not found")
        return {"success": True, "message": "Errata deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete errata: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete errata",
        )


# ── 文档关联勘误查询（挂载在 documents router 下） ──

async def get_document_errata(
    document_id: UUID,
    errata_service: Annotated[ErrataService, Depends(get_errata_service)],
) -> dict:
    """查询文档关联的勘误 — 供 RAG 检索结果标记使用"""
    errata_list = await errata_service.get_errata_for_document(str(document_id))
    return {
        "success": True,
        "data": {
            "document_id": str(document_id),
            "errata_list": [_errata_to_dict(e) for e in errata_list],
            "total_count": len(errata_list),
        },
    }
