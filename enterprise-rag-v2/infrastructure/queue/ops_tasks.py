"""
运维中心异步任务（P0 骨架）
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from databases import Database
from sqlalchemy import select

from core.config import get_settings
from infrastructure.database.models import Dataset, Document, Workspace
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import run_coroutine
from infrastructure.cache import get_cache
from infrastructure.repositories.document_repository import DocumentRepositoryImpl
from services.impl.document_service import DocumentServiceImpl
from apps.commercialization.services.quota_service import QuotaService
from services.ops.cache_invalidation import invalidate_ops_caches

logger = get_logger("infrastructure.queue.ops_tasks")


async def _write_event(
    db: Database,
    operation_id: str,
    task_id: str,
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO ops_task_events (
            id, operation_id, task_id, event_type, message, payload, retry_count, error_code, created_at
        )
        VALUES (
            :id, :operation_id, :task_id, :event_type, :message, :payload, 0, NULL, :created_at
        )
        """,
        {
            "id": str(uuid4()),
            "operation_id": operation_id,
            "task_id": task_id,
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
            "created_at": datetime.now(timezone.utc),
        },
    )


async def _process_one_document_for_ops(document_id_str: str) -> bool:
    """与 document_tasks.process_document_task 相同：走完整提取/分块/向量化链路。"""
    async with AsyncSessionLocal() as session:
        document_service = DocumentServiceImpl(session)
        return await document_service.process_document(document_id_str)


async def _tenant_id_for_dataset(session, dataset_id: str) -> str | None:
    result = await session.execute(
        select(Workspace.tenant_id)
        .join(Dataset, Dataset.workspace_id == Workspace.id)
        .where(Dataset.id == dataset_id)
    )
    row = result.first()
    return str(row[0]) if row else None


async def _list_document_ids_by_tenant(session, tenant_id: str) -> list[str]:
    result = await session.execute(
        select(Document.id)
        .join(Dataset, Document.dataset_id == Dataset.id)
        .join(Workspace, Dataset.workspace_id == Workspace.id)
        .where(Workspace.tenant_id == tenant_id)
    )
    return [str(row[0]) for row in result.all()]


async def _resolve_reindex_document_ids(payload: dict) -> list[str]:
    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id:
        raise ValueError("缺少 tenant_id")
    document_id = payload.get("document_id")
    dataset_id = payload.get("dataset_id")

    async with AsyncSessionLocal() as session:
        repo = DocumentRepositoryImpl(session)

        if document_id:
            did = str(document_id).strip()
            doc = await repo.get_by_id(did)
            if not doc:
                raise ValueError(f"文档不存在: {did}")
            t = await _tenant_id_for_dataset(session, str(doc.dataset_id))
            if t is None or t != tenant_id:
                raise ValueError("document 不属于指定 tenant_id")
            return [did]

        if dataset_id:
            dsid = str(dataset_id).strip()
            t = await _tenant_id_for_dataset(session, dsid)
            if t is None:
                raise ValueError(f"数据集不存在: {dsid}")
            if t != tenant_id:
                raise ValueError("dataset 不属于指定 tenant_id")
            docs = await repo.get_by_dataset(UUID(dsid))
            return [str(d.id) for d in docs]

        return await _list_document_ids_by_tenant(session, tenant_id)


async def _execute_reindex_documents(
    task_id: str,
    db: Database,
    operation_id: str,
    payload: dict,
) -> dict[str, Any]:
    doc_ids = await _resolve_reindex_document_ids(payload)
    total = len(doc_ids)
    processed = 0
    failed = 0
    errors: list[dict[str, Any]] = []

    for idx, did in enumerate(doc_ids, start=1):
        if operation_id:
            await _write_event(
                db,
                operation_id,
                task_id,
                "PROGRESS",
                f"reindex {idx}/{total}",
                {"document_id": did, "index": idx, "total": total},
            )
        try:
            ok = await _process_one_document_for_ops(did)
            if ok:
                processed += 1
            else:
                failed += 1
                errors.append({"document_id": did, "error": "process_document returned False"})
        except Exception as e:
            failed += 1
            errors.append({"document_id": did, "error": str(e)[:500]})
            logger.warning("ops_reindex document failed: %s", e, exc_info=True)

    return {
        "total": total,
        "processed": processed,
        "failed": failed,
        "errors": errors[:50],
    }


async def _run_ops_reindex(task_id: str, payload: dict) -> dict:
    settings = get_settings()
    db = Database(settings.database.url)
    await db.connect()
    operation_id = str(payload.get("operation_id") or "")
    try:
        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'RUNNING', updated_at = :updated_at
                WHERE operation_id = :operation_id
                """,
                {"operation_id": operation_id, "updated_at": datetime.now(timezone.utc)},
            )
            await _write_event(db, operation_id, task_id, "STARTED", "reindex task started", payload)

        summary = await _execute_reindex_documents(task_id, db, operation_id, payload)
        done_payload = {**payload, "result": summary}

        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'SUCCEEDED', updated_at = :updated_at, finished_at = :finished_at
                WHERE operation_id = :operation_id
                """,
                {
                    "operation_id": operation_id,
                    "updated_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            )
            await _write_event(db, operation_id, task_id, "SUCCEEDED", "reindex task succeeded", done_payload)

        return {"success": True, "payload": payload, "result": summary}
    except Exception as e:
        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'FAILED', error_message = :error_message, updated_at = :updated_at, finished_at = :finished_at
                WHERE operation_id = :operation_id
                """,
                {
                    "operation_id": operation_id,
                    "error_message": str(e)[:2000],
                    "updated_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            )
            await _write_event(db, operation_id, task_id, "FAILED", "reindex task failed", {"error": str(e)})
        raise
    finally:
        await db.disconnect()


async def _run_ops_sync_tenant_cache(task_id: str, payload: dict) -> dict:
    settings = get_settings()
    db = Database(settings.database.url)
    await db.connect()
    operation_id = str(payload.get("operation_id") or "")
    tenant_id = str(payload.get("tenant_id") or "").strip()
    try:
        if not tenant_id:
            raise ValueError("缺少 tenant_id")

        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'RUNNING', updated_at = :updated_at
                WHERE operation_id = :operation_id
                """,
                {"operation_id": operation_id, "updated_at": datetime.now(timezone.utc)},
            )
            await _write_event(db, operation_id, task_id, "STARTED", "sync tenant cache started", payload)

        redis = await get_cache()
        invalidate_summary = await invalidate_ops_caches(
            redis,
            scopes=["quota_overrides", "tenant_meta"],
            tenant_id=tenant_id,
        )

        if operation_id:
            await _write_event(
                db,
                operation_id,
                task_id,
                "PROGRESS",
                "tenant cache redis keys refreshed",
                {"tenant_id": tenant_id, "invalidate": invalidate_summary},
            )
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'SUCCEEDED', updated_at = :updated_at, finished_at = :finished_at
                WHERE operation_id = :operation_id
                """,
                {
                    "operation_id": operation_id,
                    "updated_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            )
            await _write_event(
                db,
                operation_id,
                task_id,
                "SUCCEEDED",
                "sync tenant cache succeeded",
                {**payload, "invalidate": invalidate_summary},
            )

        return {"success": True, "payload": payload, "invalidate": invalidate_summary}
    except Exception as e:
        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'FAILED', error_message = :error_message, updated_at = :updated_at, finished_at = :finished_at
                WHERE operation_id = :operation_id
                """,
                {
                    "operation_id": operation_id,
                    "error_message": str(e)[:2000],
                    "updated_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            )
            await _write_event(db, operation_id, task_id, "FAILED", "sync tenant cache failed", {"error": str(e)})
        raise
    finally:
        await db.disconnect()


async def _run_ops_recalculate_quota(task_id: str, payload: dict) -> dict:
    settings = get_settings()
    db = Database(settings.database.url)
    await db.connect()
    operation_id = str(payload.get("operation_id") or "")
    tenant_id = str(payload.get("tenant_id") or "").strip()
    try:
        if not tenant_id:
            raise ValueError("缺少 tenant_id")

        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'RUNNING', updated_at = :updated_at
                WHERE operation_id = :operation_id
                """,
                {"operation_id": operation_id, "updated_at": datetime.now(timezone.utc)},
            )
            await _write_event(db, operation_id, task_id, "STARTED", "recalculate quota started", payload)

        redis = await get_cache()
        quota_svc = QuotaService(db, redis)
        invalidate_summary = await invalidate_ops_caches(
            redis,
            scopes=["quota_overrides"],
            tenant_id=tenant_id,
        )
        usage_snapshot = await quota_svc.get_usage_info(tenant_id)

        if operation_id:
            await _write_event(
                db,
                operation_id,
                task_id,
                "PROGRESS",
                "quota usage snapshot computed",
                {"tenant_id": tenant_id, "invalidate": invalidate_summary, "usage": usage_snapshot},
            )
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'SUCCEEDED', updated_at = :updated_at, finished_at = :finished_at
                WHERE operation_id = :operation_id
                """,
                {
                    "operation_id": operation_id,
                    "updated_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            )
            await _write_event(
                db,
                operation_id,
                task_id,
                "SUCCEEDED",
                "recalculate quota succeeded",
                {
                    **payload,
                    "invalidate": invalidate_summary,
                    "usage": usage_snapshot,
                },
            )

        return {
            "success": True,
            "payload": payload,
            "invalidate": invalidate_summary,
            "usage": usage_snapshot,
        }
    except Exception as e:
        if operation_id:
            await db.execute(
                """
                UPDATE ops_operations
                SET status = 'FAILED', error_message = :error_message, updated_at = :updated_at, finished_at = :finished_at
                WHERE operation_id = :operation_id
                """,
                {
                    "operation_id": operation_id,
                    "error_message": str(e)[:2000],
                    "updated_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                },
            )
            await _write_event(db, operation_id, task_id, "FAILED", "recalculate quota failed", {"error": str(e)})
        raise
    finally:
        await db.disconnect()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def ops_reindex_documents(self, payload: dict):
    """
    运维触发重建索引：按 payload 调用 DocumentServiceImpl.process_document，
    与 document_tasks 处理链路一致（提取文本 / 分块 / 向量化）。
    payload 须含 tenant_id；可选 document_id（单文档）或 dataset_id（数据集内全部），
    否则处理该租户下全部文档。tenant 与 document/dataset 会做一致性校验。
    """
    return run_coroutine(_run_ops_reindex(self.request.id, payload))


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def ops_sync_tenant_cache(self, payload: dict):
    """租户缓存同步任务（P0 占位链路）。"""
    return run_coroutine(_run_ops_sync_tenant_cache(self.request.id, payload))


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def ops_recalculate_quota(self, payload: dict):
    """租户配额重算任务（P0 占位链路）。"""
    return run_coroutine(_run_ops_recalculate_quota(self.request.id, payload))

