"""
文档路由

处理文档管理相关的API端点
"""

from typing import Annotated, List, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from pydantic import BaseModel
import json

from api.schemas.base import BaseResponse, DataResponse, PaginatedResponse
from api.schemas.document import (
    DocumentUploadRequest,
    DocumentUploadToDatasetRequest,
    DocumentUpdateRequest,
    DocumentQueryRequest,
    DocumentInfo,
    DocumentStatistics,
)
from api.schemas.annotation import DocumentAnnotationCreateRequest, DocumentAnnotationListResponse, DocumentAnnotationResponse
from api.deps import get_document_service, get_dataset_service, get_current_active_user, get_quota_service, get_db
from apps.commercialization.models import QuotaExceededError
from services.interfaces.document_service import DocumentService
from services.interfaces.dataset_service import DatasetService
from core.value_objects.pagination import Pagination
from infrastructure.logging.logger import get_logger
from infrastructure.queue.document_tasks import process_document_task
from infrastructure.database.models import DocumentAnnotation, Dataset
from sqlalchemy import select

logger = get_logger("api.routers.documents")


router = APIRouter()


class DocumentOriginalTextResponse(BaseModel):
    text: str


def _annotation_payload(annotation: DocumentAnnotation) -> dict:
    return {
        "id": str(annotation.id),
        "document_id": str(annotation.document_id),
        "author_id": str(annotation.author_id),
        "kind": annotation.kind,
        "quote": annotation.quote or "",
        "body": annotation.body,
        "question": annotation.question,
        "created_at": annotation.created_at,
        "updated_at": annotation.updated_at,
    }


async def _verify_document_access(
    document_id: UUID,
    current_user: dict,
    document_service: DocumentService,
    dataset_service: DatasetService,
    action: str = "read",
) -> dict:
    """加载文档并在路由层统一执行租户/工作空间访问校验。"""
    document = await document_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    dataset_id = document.get("dataset_id")
    if not dataset_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Document has no dataset")
    try:
        await dataset_service.verify_dataset_access(
            dataset_id=UUID(str(dataset_id)),
            user_id=current_user["sub"],
            tenant_id=str(current_user.get("tenant_id", "")),
            action=action,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return document


@router.post("/", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: DocumentUploadRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
):
    """上传文档"""
    try:
        dataset_id = UUID(request.dataset_id)
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=current_user["sub"],
            tenant_id=str(current_user.get("tenant_id", "")),
            action="write",
        )
        result = await document_service.upload_document(
            dataset_id=dataset_id,
            file_path="",
            file_name=request.file_name,
            file_type=request.file_type.value,
            file_size=0,
            tags=request.tags,
            metadata=request.metadata
        )
        return DataResponse(success=True, message="Document uploaded successfully", data=result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to upload document: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload document")


@router.get("/")
async def list_documents(
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    dataset_id: UUID = None,
    document_status: str = Query(None, alias="status"),
    file_type: str = None,
    knowledge_type: str = None,
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """查询文档列表"""
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dataset_id is required")
    await dataset_service.verify_dataset_access(
        dataset_id=dataset_id,
        user_id=current_user["sub"],
        tenant_id=str(current_user.get("tenant_id", "")),
        action="read",
    )
    pagination = Pagination(page=page, page_size=page_size)
    result = await document_service.list_documents(
        dataset_id=dataset_id,
        status=document_status,
        file_type=file_type,
        knowledge_type=knowledge_type,
        keyword=keyword,
        pagination=pagination
    )

    return {
        "success": True,
        "data": {
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size
        }
    }


@router.get("/datasets/{dataset_id}")
async def list_documents_by_dataset(
    dataset_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    status: str = None,
    file_type: str = None,
    knowledge_type: str = None,
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """查询指定数据集的文档列表"""
    await dataset_service.verify_dataset_access(
        dataset_id=dataset_id,
        user_id=current_user["sub"],
        tenant_id=str(current_user.get("tenant_id", "")),
        action="read",
    )
    pagination = Pagination(page=page, page_size=page_size)
    result = await document_service.list_documents(
        dataset_id=dataset_id,
        status=status,
        file_type=file_type,
        knowledge_type=knowledge_type,
        keyword=keyword,
        pagination=pagination
    )

    return {
        "success": True,
        "data": {
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size
        }
    }


async def _upload_document_to_dataset_impl(
    dataset_id: UUID,
    file: UploadFile,
    process_rule: str | None,
    document_service: DocumentService,
    quota_service,
    tenant_id: str,
) -> DataResponse:
    import uuid
    from pathlib import Path

    upload_dir = Path("./uploads")
    upload_dir.mkdir(exist_ok=True)

    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = upload_dir / unique_filename

    file_size = 0
    with open(file_path, "wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)
            file_size += len(chunk)

    if quota_service is not None:
        await quota_service.assert_can_add_document(tenant_id, file_size)

    rule_data = {}
    if process_rule:
        try:
            rule_data = json.loads(process_rule)
        except json.JSONDecodeError:
            pass

    result = await document_service.upload_document(
        dataset_id=dataset_id,
        file_path=str(file_path),
        file_name=file.filename,
        file_type=file_ext,
        file_size=file_size,
        tags=rule_data.get('tags'),
        metadata=rule_data.get('metadata'),
        knowledge_type=rule_data.get('knowledge_type'),
    )

    logger.info(f"文档创建成功, document_id={result.get('id')}")

    # 必须在分发 Celery 任务前 commit，否则 worker 的新 session 看不到文档
    await document_service.session.commit()

    document_id = result.get("id")
    if document_id:
        try:
            async_result = process_document_task.apply_async(
                args=[str(document_id)],
                queue="documents_high",
            )
            logger.info(
                f"文档处理任务已入队, document_id={document_id}, celery_task_id={async_result.id}"
            )
        except Exception as e:
            logger.warning(
                f"文档已保存但Celery任务提交失败, document_id={document_id}, error={e}"
            )

    return DataResponse(success=True, message="Document uploaded successfully", data=result)


@router.post(
    "/datasets/{dataset_id}",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/datasets/{dataset_id}/",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document_to_dataset(
    dataset_id: UUID,
    file: UploadFile = File(...),
    process_rule: str = Form(default=None),
    current_user: Annotated[dict, Depends(get_current_active_user)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)] = None,
    quota_service: Annotated[Any, Depends(get_quota_service)] = None,
):
    """上传文档到指定数据集（同时接受有无尾斜杠，避免 307 重定向破坏 multipart）。"""
    tenant_id = current_user.get("tenant_id") if current_user else None
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户缺少租户信息，无法校验配额",
        )
    try:
        # 验证写权限（公开数据集拒绝非成员写入）
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=current_user["sub"],
            tenant_id=str(tenant_id),
            action="write",
        )
        return await _upload_document_to_dataset_impl(
            dataset_id, file, process_rule, document_service, quota_service, str(tenant_id)
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except QuotaExceededError:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError, OSError) as e:
        logger.exception("Upload document failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )
    except Exception as e:
        logger.exception("Unexpected error during document upload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )


@router.post("/batch-delete")
async def batch_delete_documents(
    request: dict,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
):
    """批量删除文档"""
    tenant_id = str(current_user.get("tenant_id", ""))
    user_id = current_user["sub"]
    document_ids = [UUID(doc_id) for doc_id in request.get("document_ids", [])]
    for doc_id in document_ids:
        doc = await document_service.get_document(doc_id)
        if doc and doc.get("dataset_id"):
            await dataset_service.verify_dataset_access(
                dataset_id=UUID(doc["dataset_id"]),
                user_id=user_id,
                tenant_id=tenant_id,
                action="write",
            )
    result = await document_service.batch_delete_documents(document_ids)
    return {"success": True, "data": result}


@router.get("/statistics")
async def get_document_statistics(
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    dataset_id: UUID = None
):
    """获取文档统计信息"""
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dataset_id is required")
    await dataset_service.verify_dataset_access(
        dataset_id=dataset_id,
        user_id=current_user["sub"],
        tenant_id=str(current_user.get("tenant_id", "")),
        action="read",
    )
    result = await document_service.get_document_statistics(dataset_id)
    return {"success": True, "data": result}


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """获取文档详情"""
    result = await _verify_document_access(document_id, current_user, document_service, dataset_service)
    return {"success": True, "data": result}


@router.get("/{document_id}/segments")
async def get_document_segments(
    document_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取文档分段列表"""
    await _verify_document_access(document_id, current_user, document_service, dataset_service)
    result = await document_service.get_document_segments(
        document_id=document_id,
        page=page,
        page_size=page_size
    )

    return {
        "success": True,
        "data": {
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size
        }
    }


@router.get("/{document_id}/original-text", response_model=DataResponse[DocumentOriginalTextResponse])
async def get_document_original_text(
    document_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """获取文档原始文本（直接从上传文件提取）"""
    try:
        await _verify_document_access(document_id, current_user, document_service, dataset_service)
        text = await document_service.get_document_original_text(document_id)
        return DataResponse(
            success=True,
            data=DocumentOriginalTextResponse(text=text)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (RuntimeError, TypeError, AttributeError, OSError) as e:
        logger.exception(f"获取文档原文失败, document_id={document_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document original text",
        )


@router.get("/{document_id}/annotations", response_model=DocumentAnnotationListResponse)
async def list_document_annotations(
    document_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """读取文档阅读台标注，按文档权限隔离。"""
    await _verify_document_access(document_id, current_user, document_service, dataset_service)
    result = await db.execute(
        select(DocumentAnnotation)
        .where(DocumentAnnotation.document_id == str(document_id))
        .order_by(DocumentAnnotation.created_at.desc())
    )
    items = [_annotation_payload(item) for item in result.scalars().all()]
    return {"items": items, "total": len(items)}


@router.post("/{document_id}/annotations", response_model=DocumentAnnotationResponse, status_code=status.HTTP_201_CREATED)
async def create_document_annotation(
    document_id: UUID,
    request: DocumentAnnotationCreateRequest,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """创建阅读笔记或理解标注。"""
    document = await _verify_document_access(document_id, current_user, document_service, dataset_service, action="write")
    dataset_result = await db.execute(select(Dataset).where(Dataset.id == str(document["dataset_id"])))
    dataset = dataset_result.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    annotation = DocumentAnnotation(
        tenant_id=str(current_user.get("tenant_id")),
        workspace_id=str(dataset.workspace_id),
        document_id=str(document_id),
        author_id=str(current_user["sub"]),
        kind=request.kind,
        quote=request.quote.strip(),
        body=request.body.strip(),
        question=request.question.strip() if request.question else None,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return _annotation_payload(annotation)


@router.delete("/{document_id}/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_annotation(
    document_id: UUID,
    annotation_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """删除本人创建的阅读标注。"""
    await _verify_document_access(document_id, current_user, document_service, dataset_service, action="write")
    result = await db.execute(
        select(DocumentAnnotation).where(
            DocumentAnnotation.id == str(annotation_id),
            DocumentAnnotation.document_id == str(document_id),
            DocumentAnnotation.author_id == str(current_user["sub"]),
        )
    )
    annotation = result.scalar_one_or_none()
    if annotation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
    await db.delete(annotation)
    await db.commit()
    return None


@router.put("/{document_id}")
async def update_document(
    document_id: UUID,
    request: DocumentUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
):
    """更新文档"""
    try:
        doc = await document_service.get_document(document_id)
        if doc and doc.get("dataset_id"):
            await dataset_service.verify_dataset_access(
                dataset_id=UUID(doc["dataset_id"]),
                user_id=current_user["sub"],
                tenant_id=str(current_user.get("tenant_id", "")),
                action="write",
            )
        update_data = request.model_dump(exclude_unset=True)
        result = await document_service.update_document(document_id, **update_data)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update document %s: %s", document_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update document")


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
):
    """删除文档"""
    doc = await document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.get("dataset_id"):
        try:
            await dataset_service.verify_dataset_access(
                dataset_id=UUID(doc["dataset_id"]),
                user_id=current_user["sub"],
                tenant_id=str(current_user.get("tenant_id", "")),
                action="write",
            )
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    success = await document_service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"success": True, "message": "Document deleted successfully"}


@router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    request: dict = None
):
    """重新索引文档"""
    try:
        doc = await document_service.get_document(document_id)
        if doc and doc.get("dataset_id"):
            await dataset_service.verify_dataset_access(
                dataset_id=UUID(doc["dataset_id"]),
                user_id=current_user["sub"],
                tenant_id=str(current_user.get("tenant_id", "")),
                action="write",
            )
        force = request.get("force", False) if request else False
        result = await document_service.reindex_document(document_id, force)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to reindex document %s: %s", document_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reindex document")


@router.post("/{document_id}/process")
async def process_document(
    document_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
):
    """处理文档"""
    doc = await document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.get("dataset_id"):
        try:
            await dataset_service.verify_dataset_access(
                dataset_id=UUID(doc["dataset_id"]),
                user_id=current_user["sub"],
                tenant_id=str(current_user.get("tenant_id", "")),
                action="write",
            )
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    success = await document_service.process_document(document_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"success": True, "message": "Document processing started"}


@router.get("/{document_id}/errata")
async def get_document_errata(
    document_id: UUID,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """获取文档关联的勘误列表"""
    from services.impl.errata_service import ErrataService, get_errata_service
    from api.routers.errata import _errata_to_dict

    doc = await _verify_document_access(document_id, current_user, document_service, dataset_service)

    async for errata_service in get_errata_service():
        errata_list = await errata_service.get_errata_for_document(str(document_id))
        return {
            "success": True,
            "data": {
                "document_id": str(document_id),
                "document_name": doc.get("file_name", ""),
                "errata_list": [_errata_to_dict(e) for e in errata_list],
                "total_count": len(errata_list),
            },
        }


class WechatImportResponse(BaseModel):
    document_id: str
    file_name: str
    total_messages: int
    participants: list
    date_range: tuple
    format_detected: str


@router.post(
    "/import/wechat",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_wechat_chat(
    dataset_id: UUID = Form(...),
    file: UploadFile = File(...),
    chat_name: str = Form(default=""),
    current_user: Annotated[dict, Depends(get_current_active_user)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)] = None,
    quota_service: Annotated[Any, Depends(get_quota_service)] = None,
):
    """导入微信聊天记录

    接受 WeChatMsg 等工具导出的 TXT/CSV 文件，
    解析后转为可检索的知识库文档。
    """
    import uuid
    from pathlib import Path
    from core.rag.wechat_parser import WechatChatParser

    tenant_id = current_user.get("tenant_id") if current_user else None
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户缺少租户信息",
        )

    # 验证写权限（公开数据集拒绝非成员写入）
    try:
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=current_user["sub"],
            tenant_id=str(tenant_id),
            action="write",
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    # 校验文件类型
    file_ext = (file.filename or "").split(".")[-1].lower() if file.filename else ""
    if file_ext not in ("txt", "csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .txt 或 .csv 格式的微信聊天记录文件",
        )

    # 读取上传文件
    raw_bytes = await file.read()
    try:
        raw_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            raw_content = raw_bytes.decode("gbk")
        except (UnicodeDecodeError, LookupError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件编码不支持，请使用 UTF-8 或 GBK 编码导出",
            )

    # 解析聊天记录
    parser = WechatChatParser()
    result = parser.parse_content(raw_content)

    if result.total_messages == 0:
        detail = "未能解析出聊天消息"
        if result.errors:
            detail += f": {result.errors[0]}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    # 生成适合检索的文本
    chat_label = chat_name or (file.filename or "微信聊天记录")
    document_text = parser.to_document_text(result, chat_name=chat_label)

    # 写入临时文件，复用现有文档处理管线
    upload_dir = Path("./uploads")
    upload_dir.mkdir(exist_ok=True)

    doc_file_name = f"{chat_label}.txt"
    unique_filename = f"{uuid.uuid4()}.txt"
    tmp_path = upload_dir / unique_filename

    file_size = len(document_text.encode("utf-8"))
    tmp_path.write_text(document_text, encoding="utf-8")

    if quota_service is not None:
        await quota_service.assert_can_add_document(tenant_id, file_size)

    doc_result = await document_service.upload_document(
        dataset_id=dataset_id,
        file_path=str(tmp_path),
        file_name=doc_file_name,
        file_type="txt",
        file_size=file_size,
        tags=["wechat-import"],
        metadata={
            "source": "wechat_import",
            "total_messages": result.total_messages,
            "participants": result.participants,
            "format_detected": result.format_detected,
            "date_range": list(result.date_range) if result.date_range else [],
        },
    )

    # 必须在分发 Celery 任务前 commit，否则 worker 的新 session 看不到文档
    await document_service.session.commit()

    document_id = doc_result.get("id")
    if document_id:
        try:
            process_document_task.apply_async(
                args=[str(document_id)],
                queue="documents_high",
            )
            logger.info(
                f"微信聊天记录导入已入队, document_id={document_id}, "
                f"messages={result.total_messages}, participants={result.participants}"
            )
        except Exception as e:
            logger.warning(f"微信导入文档已保存但 Celery 任务提交失败: {e}")

    return DataResponse(
        success=True,
        message=f"成功导入 {result.total_messages} 条聊天记录",
        data={
            "document_id": str(document_id) if document_id else None,
            "file_name": doc_file_name,
            "total_messages": result.total_messages,
            "participants": result.participants,
            "date_range": list(result.date_range) if result.date_range else [],
            "format_detected": result.format_detected,
        },
    )
