"""内容排期的 Celery Worker 入口。"""

from infrastructure.database.session import AsyncSessionLocal
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import run_coroutine
from services.impl.content_publishing_service import ContentPublishingService
from services.impl.content_metric_sync_service import ContentMetricSyncService


async def _dispatch_due_schedules_async() -> int:
    async with AsyncSessionLocal() as session:
        count = await ContentPublishingService(session).dispatch_due_schedules()
        await session.commit()
        return count


@celery_app.task(name="content.dispatch_due_schedules")
def dispatch_due_content_schedules() -> int:
    return run_coroutine(_dispatch_due_schedules_async())


async def _sync_metric_snapshot_async(run_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        result = await ContentMetricSyncService(session).execute(run_id=run_id)
        await session.commit()
        return result or {"id": run_id, "status": "missing"}


@celery_app.task(name="content.sync_metric_snapshot")
def sync_metric_snapshot(run_id: str) -> dict:
    return run_coroutine(_sync_metric_snapshot_async(run_id))
