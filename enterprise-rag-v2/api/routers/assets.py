"""AI 工作台素材元数据入口。"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.asset import (
    AssetCreateRequest,
    AssetImportUrlRequest,
    AssetImportUrlBatchRequest,
    AssetIngestionResponse,
    AssetOrganizeResponse,
    AssetBatchResponse,
    AssetListResponse,
    KnowledgePackageImportRequest,
    AssetProcessingStatusResponse,
    AssetResponse,
    AssetTextIngestionRequest,
)
from services.impl.asset_service import AssetServiceImpl
from services.impl.asset_ingestion_service import AssetIngestionService
from services.impl.safe_fetcher import UnsafeUrlError, validate_content_type
from infrastructure.queue.asset_tasks import ingest_asset_url_task, process_asset_document_task, retry_asset_task
from infrastructure.queue.knowledge_tasks import organize_asset_task
from services.impl.agent_runtime_service import AgentRuntimeService


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    request: AssetCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    service = AssetServiceImpl(db)
    try:
        return await service.create_asset(
            tenant_id=parse_tenant_uuid_from_user(current_user),
            workspace_id=request.workspace_id,
            dataset_id=request.dataset_id,
            user_id=_user_id(current_user),
            source_type=request.source_type,
            title=request.title,
            source_uri=request.source_uri,
            mime_type=request.mime_type,
            size_bytes=request.size_bytes,
            content_hash=request.content_hash,
            metadata=request.metadata,
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/import-batch", response_model=AssetBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_asset_batch(
    workspace_id: UUID = Form(...),
    dataset_id: Optional[UUID] = Form(None),
    files: list[UploadFile] = File(...),
    current_user: Annotated[dict, Depends(get_current_active_user)] = None,
    db=Depends(get_db),
):
    """批量导入文件；自动绑定默认资料库，单项失败不影响其他文件。"""
    if not files or len(files) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="一次最多导入 50 个文件")
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    asset_service = AssetServiceImpl(db)
    try:
        selected_dataset = dataset_id or await asset_service.ensure_default_dataset(
            workspace_id=workspace_id, tenant_id=tenant_id, user_id=user_id, is_superuser=bool(current_user.get("is_superuser"))
        )
        batch = await asset_service.create_ingestion_batch(
            tenant_id=tenant_id, workspace_id=workspace_id, dataset_id=selected_dataset,
            user_id=user_id, total_count=len(files), options_json={"auto_organize": True},
        )
        max_bytes = 20 * 1024 * 1024
        pending_tasks: list[tuple[str, str]] = []
        for file in files:
            title = file.filename or "未命名文件"
            asset = await asset_service.create_asset(
                tenant_id=tenant_id, workspace_id=workspace_id, dataset_id=selected_dataset, batch_id=UUID(str(batch.id)),
                user_id=user_id, source_type="file", title=title, mime_type=file.content_type,
                metadata={"batch_id": str(batch.id), "auto_organize": True}, is_superuser=bool(current_user.get("is_superuser")),
            )
            try:
                content = await file.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise ValueError("文件大小超过 20MB 限制")
                if not content:
                    raise ValueError("文件内容不能为空")
                result = await AssetIngestionService(db).ingest_bytes(
                    asset_id=UUID(str(asset["id"])), tenant_id=tenant_id, user_id=user_id,
                    content=content, content_type=file.content_type, is_superuser=bool(current_user.get("is_superuser")),
                )
                if result.get("document_id"):
                    pending_tasks.append((str(asset["id"]), result["document_id"]))
            except Exception as exc:
                await asset_service.mark_asset_failed(str(asset["id"]), str(exc)[:2000])
        await db.commit()
        await db.refresh(batch)
        for asset_id, document_id in pending_tasks:
            process_asset_document_task.apply_async(
                args=[asset_id, document_id, str(tenant_id)], queue="documents_high"
            )
        return await asset_service.build_batch_response(batch)
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/batches/{batch_id}", response_model=AssetBatchResponse)
async def get_asset_batch(
    batch_id: UUID,
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    service = AssetServiceImpl(db)
    try:
        batch = await service.get_ingestion_batch(
            batch_id=batch_id,
            workspace_id=workspace_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入批次不存在")
    payload = await service.build_batch_response(batch)
    await db.commit()
    return payload


@router.post("/batches/{batch_id}/retry-failed", response_model=AssetBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_batch(
    batch_id: UUID,
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """重新提交批次中失败或已卡住的素材，成功项保持不变。"""
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    service = AssetServiceImpl(db)
    try:
        batch = await service.get_ingestion_batch(
            batch_id=batch_id, workspace_id=workspace_id, tenant_id=tenant_id,
            user_id=user_id, is_superuser=bool(current_user.get("is_superuser")),
        )
        if batch is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入批次不存在")
        pending = await service.retry_batch_assets(
            batch=batch, tenant_id=tenant_id, user_id=user_id,
            is_superuser=bool(current_user.get("is_superuser")),
        )
        await db.commit()
        for asset_id in pending:
            retry_asset_task.delay(asset_id, str(tenant_id), str(user_id), bool(current_user.get("is_superuser")))
        await db.refresh(batch)
        payload = await service.build_batch_response(batch)
        await db.commit()
        return payload
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/import-knowledge-package", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def import_knowledge_package(
    request: KnowledgePackageImportRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """登记外部授权知识包，并保留 verified/unverified 门禁状态。"""
    tenant_id = parse_tenant_uuid_from_user(current_user)
    try:
        metadata = request.as_asset_metadata()
        return await AssetServiceImpl(db).create_asset(
            tenant_id=tenant_id,
            workspace_id=request.workspace_id,
            dataset_id=request.dataset_id,
            user_id=_user_id(current_user),
            source_type="text",
            title=request.title,
            source_uri=f"knowledge-package://{request.package_id}",
            mime_type="application/json",
            metadata=metadata,
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=AssetListResponse)
async def list_assets(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    asset_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        return await AssetServiceImpl(db).list_assets(
            tenant_id=parse_tenant_uuid_from_user(current_user),
            workspace_id=workspace_id,
            user_id=_user_id(current_user),
            page=page,
            page_size=page_size,
            asset_status=asset_status,
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/import-url", response_model=AssetIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_asset_url(
    request: AssetImportUrlRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """创建 URL 素材并立即提交受控抓取任务。"""
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    try:
        asset = await AssetServiceImpl(db).create_asset(
            tenant_id=tenant_id,
            workspace_id=request.workspace_id,
            dataset_id=request.dataset_id,
            user_id=user_id,
            source_type="url",
            title=request.title,
            source_uri=request.source_uri,
            metadata=request.metadata,
            is_superuser=bool(current_user.get("is_superuser")),
        )
        await db.commit()
        task = ingest_asset_url_task.delay(
            str(asset["id"]), str(tenant_id), str(user_id), bool(current_user.get("is_superuser")),
        )
        return {"asset_id": asset["id"], "status": "processing", "task_id": task.id}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/import-urls", response_model=AssetBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_asset_urls(
    request: AssetImportUrlBatchRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """批量导入 URL；每行一个地址，复用安全抓取和统一批次状态。"""
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    urls = list(dict.fromkeys(item.strip() for item in request.urls if item.strip()))
    if not urls or len(urls) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="一次最多导入 50 个 URL")
    service = AssetServiceImpl(db)
    try:
        selected_dataset = request.dataset_id or await service.ensure_default_dataset(
            workspace_id=request.workspace_id, tenant_id=tenant_id, user_id=user_id,
            is_superuser=bool(current_user.get("is_superuser")),
        )
        batch = await service.create_ingestion_batch(
            tenant_id=tenant_id, workspace_id=request.workspace_id, dataset_id=selected_dataset,
            user_id=user_id, total_count=len(urls), options_json={"auto_organize": True, "source_type": "url"},
        )
        pending: list[str] = []
        for source_uri in urls:
            title = source_uri[:255]
            asset = await service.create_asset(
                tenant_id=tenant_id, workspace_id=request.workspace_id, dataset_id=selected_dataset,
                batch_id=UUID(str(batch.id)), user_id=user_id, source_type="url", title=title,
                source_uri=source_uri, metadata={"batch_id": str(batch.id), "auto_organize": True},
                is_superuser=bool(current_user.get("is_superuser")),
            )
            pending.append(str(asset["id"]))
        await db.commit()
        for asset_id in pending:
            ingest_asset_url_task.delay(asset_id, str(tenant_id), str(user_id), bool(current_user.get("is_superuser")))
        await db.refresh(batch)
        return await service.build_batch_response(batch)
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AssetServiceImpl(db).get_asset(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    return result


@router.post("/{asset_id}/ingest", response_model=AssetIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_asset(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """提交 URL 素材导入任务；抓取由 worker 复用 SafeFetcher 执行。"""
    try:
        asset = await AssetServiceImpl(db).get_asset(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    task = ingest_asset_url_task.delay(
        str(asset_id),
        str(parse_tenant_uuid_from_user(current_user)),
        str(_user_id(current_user)),
        bool(current_user.get("is_superuser")),
    )
    return {"asset_id": asset_id, "status": "processing", "task_id": task.id}


@router.get("/{asset_id}/processing-status", response_model=AssetProcessingStatusResponse)
async def get_asset_processing_status(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AssetServiceImpl(db).processing_status(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    return result


@router.post("/{asset_id}/organize", response_model=AssetOrganizeResponse, status_code=status.HTTP_202_ACCEPTED)
async def organize_asset(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    try:
        asset = await AssetServiceImpl(db).get_asset(asset_id=asset_id, tenant_id=tenant_id, user_id=user_id, is_superuser=bool(current_user.get("is_superuser")))
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
        if not asset.get("legacy_document_id") or asset.get("status") not in {"ready", "completed"}:
            raise ValueError("素材必须完成解析后才能提炼知识")
        agent_run = await AgentRuntimeService(db).create_asset_organize_run(asset_id=asset_id, tenant_id=tenant_id, workspace_id=UUID(str(asset["workspace_id"])), user_id=user_id)
        await AssetServiceImpl(db).bind_agent_run(asset_id=asset_id, tenant_id=tenant_id, user_id=user_id, agent_run_id=UUID(str(agent_run.id)), is_superuser=bool(current_user.get("is_superuser")))
        await db.commit()
        task = organize_asset_task.delay(str(asset_id), str(tenant_id), str(user_id))
        return {"asset_id": asset_id, "agent_run_id": agent_run.id, "status": "queued", "task_id": task.id}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{asset_id}/retry", response_model=AssetIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_asset(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        result = await AssetServiceImpl(db).prepare_retry(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
        await db.commit()
        task = retry_asset_task.delay(
            str(asset_id),
            str(parse_tenant_uuid_from_user(current_user)),
            str(_user_id(current_user)),
            bool(current_user.get("is_superuser")),
        )
        return {"asset_id": asset_id, "status": "processing", "task_id": task.id}
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{asset_id}/upload", response_model=AssetResponse)
async def upload_asset(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    """将文件安全写入对象存储；后续解析任务消费 ready 素材。"""
    max_bytes = 20 * 1024 * 1024
    try:
        content_type = validate_content_type(file.content_type, file.filename or "")
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件大小超过 20MB 限制")
        chunks.append(chunk)
    try:
        result = await AssetIngestionService(db).ingest_bytes(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            content=b"".join(chunks),
            content_type=content_type,
            is_superuser=bool(current_user.get("is_superuser")),
        )
        await db.commit()
        if result.get("document_id"):
            process_asset_document_task.apply_async(
                args=[str(asset_id), result["document_id"], str(parse_tenant_uuid_from_user(current_user))],
                queue="documents_high",
            )
        return result
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{asset_id}/text", response_model=AssetResponse)
async def ingest_asset_text(
    asset_id: UUID,
    request: AssetTextIngestionRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """将用户粘贴的纯文本写入素材存储，并复用现有文档处理链路。"""
    try:
        result = await AssetIngestionService(db).ingest_bytes(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            content=request.content.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
            is_superuser=bool(current_user.get("is_superuser")),
        )
        await db.commit()
        if result.get("document_id"):
            process_asset_document_task.apply_async(
                args=[str(asset_id), result["document_id"], str(parse_tenant_uuid_from_user(current_user))],
                queue="documents_high",
            )
        return result
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        deleted = await AssetServiceImpl(db).delete_asset(
            asset_id=asset_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
