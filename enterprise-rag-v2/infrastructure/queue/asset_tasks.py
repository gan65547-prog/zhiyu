"""统一素材异步导入任务。"""

from uuid import UUID

from sqlalchemy import select

from infrastructure.database.models import Asset, AssetStatus
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import get_worker_event_loop, run_coroutine
from services.impl.asset_ingestion_service import AssetIngestionService


logger = get_logger("infrastructure.queue.asset_tasks")


async def _ingest_asset_async(asset_id: str, tenant_id: str, user_id: str, is_superuser: bool) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            result = await AssetIngestionService(session).ingest_url(
                asset_id=asset_id,
                tenant_id=tenant_id,
                user_id=user_id,
                is_superuser=is_superuser,
            )
            await session.commit()
            if result.get("document_id"):
                process_asset_document_task.apply_async(
                    args=[asset_id, result["document_id"], tenant_id],
                    queue="documents_high",
                )
            return result
        except Exception:
            await session.commit()
            raise


@celery_app.task(name="asset.ingest_url", bind=True, max_retries=2, default_retry_delay=30)
def ingest_asset_url_task(self, asset_id: str, tenant_id: str, user_id: str, is_superuser: bool = False) -> dict:
    loop = get_worker_event_loop()
    try:
        return run_coroutine(_ingest_asset_async(asset_id, tenant_id, user_id, is_superuser))
    except (ConnectionError, TimeoutError) as exc:
        logger.warning("素材 URL 导入可重试失败 asset_id=%s error=%s", asset_id, exc)
        raise self.retry(exc=exc)


async def _retry_asset_async(asset_id: str, tenant_id: str, user_id: str, is_superuser: bool) -> dict:
    async with AsyncSessionLocal() as session:
        service = AssetIngestionService(session)
        asset_result = await session.execute(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.tenant_id == tenant_id,
                Asset.deleted_at.is_(None),
            )
        )
        asset = asset_result.scalar_one_or_none()
        if asset is None:
            raise LookupError("素材不存在")
        if asset.source_type == "url":
            return await _ingest_asset_async(asset_id, tenant_id, user_id, is_superuser)
        if not asset.storage_key:
            raise ValueError("素材没有可重试的原始内容")
        await service.asset_service._verify_workspace_access(
            asset.workspace_id, tenant_id, user_id, is_superuser
        )
        asset.status = AssetStatus.PROCESSING.value
        document_id = await service._sync_legacy_document(asset)
        if document_id:
            await session.commit()
            process_asset_document_task.apply_async(
                args=[asset_id, document_id, tenant_id], queue="documents_high"
            )
            return {"asset_id": asset_id, "document_id": document_id, "status": "processing"}
        asset.status = AssetStatus.READY.value
        await session.commit()
        return {"asset_id": asset_id, "status": "ready"}


@celery_app.task(name="asset.retry", bind=True, max_retries=2, default_retry_delay=30)
def retry_asset_task(self, asset_id: str, tenant_id: str, user_id: str, is_superuser: bool = False) -> dict:
    try:
        return run_coroutine(_retry_asset_async(asset_id, tenant_id, user_id, is_superuser))
    except (ConnectionError, TimeoutError) as exc:
        logger.warning("素材重试可重试失败 asset_id=%s error=%s", asset_id, exc)
        raise self.retry(exc=exc)


async def _process_asset_document_async(asset_id: str, document_id: str, tenant_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        asset_result = await session.execute(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.tenant_id == tenant_id,
                Asset.deleted_at.is_(None),
            )
        )
        asset = asset_result.scalar_one_or_none()
        if asset is None:
            raise LookupError("素材不存在")
        try:
            from services.impl.document_service import DocumentServiceImpl

            success = await DocumentServiceImpl(session).process_document(document_id)
            if not success:
                raise RuntimeError("兼容文档处理未成功")
            asset.status = AssetStatus.READY.value
            asset.processing_error = None
            auto_organize = bool((asset.extra_metadata or {}).get("auto_organize"))
            if auto_organize:
                from services.impl.agent_runtime_service import AgentRuntimeService
                from infrastructure.queue.knowledge_tasks import organize_asset_task

                agent_run = await AgentRuntimeService(session).create_asset_organize_run(
                    asset_id=asset.id, tenant_id=UUID(str(asset.tenant_id)),
                    workspace_id=UUID(str(asset.workspace_id)), user_id=UUID(str(asset.created_by)),
                )
                metadata = dict(asset.extra_metadata or {})
                metadata["organize_agent_run_id"] = str(agent_run.id)
                asset.extra_metadata = metadata
            await session.commit()
            if auto_organize:
                organize_asset_task.delay(asset_id, tenant_id, str(asset.created_by))
            return {"asset_id": asset_id, "document_id": document_id, "status": "ready"}
        except Exception as exc:
            asset.status = AssetStatus.FAILED.value
            asset.processing_error = str(exc)[:2000]
            await session.commit()
            raise


@celery_app.task(name="asset.process_document", bind=True, max_retries=2, default_retry_delay=30)
def process_asset_document_task(self, asset_id: str, document_id: str, tenant_id: str) -> dict:
    try:
        return run_coroutine(_process_asset_document_async(asset_id, document_id, tenant_id))
    except (ConnectionError, TimeoutError) as exc:
        logger.warning("素材兼容文档处理可重试失败 asset_id=%s error=%s", asset_id, exc)
        raise self.retry(exc=exc)
