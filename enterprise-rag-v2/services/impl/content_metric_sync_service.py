"""异步平台指标快照同步：把批量导入从请求线程移到可追踪的 worker 任务。"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import ContentConnectorCredential, ContentMetricSyncRun, ContentPublishRecord
from services.impl.content_service import ContentService
from services.impl.content_connector_registry import ContentConnectorRegistry
from services.impl.content_credential_service import ContentCredentialService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentMetricSyncService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.content = ContentService(session)
        self.credentials = ContentCredentialService(session)

    @staticmethod
    def _dict(item: ContentMetricSyncRun) -> dict[str, Any]:
        return {
            "id": item.id,
            "workspace_id": item.workspace_id,
            "platform": item.platform,
            "credential_id": item.credential_id,
            "status": item.status,
            "inserted": item.inserted,
            "skipped": item.skipped,
            "error_message": item.error_message,
            "task_id": item.task_id,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
            "created_at": item.created_at,
        }

    async def create(
        self,
        *,
        workspace_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        platform: str,
        credential_id: UUID | None,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        await self.content._workspace(workspace_id, tenant_id, user_id, is_superuser)
        platform_key = platform.strip().lower()
        connector = ContentConnectorRegistry().get(platform_key)
        if not items and (connector is None or not hasattr(connector, "fetch_metrics")):
            raise ValueError("该平台尚未注册真实指标连接器；请提交人工指标快照")
        if not items and not credential_id:
            raise ValueError("读取平台真实指标必须绑定连接凭据")
        if credential_id:
            credential = await self.session.scalar(select(ContentConnectorCredential).where(
                ContentConnectorCredential.id == str(credential_id),
                ContentConnectorCredential.workspace_id == str(workspace_id),
                ContentConnectorCredential.tenant_id == str(tenant_id),
                ContentConnectorCredential.status == "active",
            ))
            if credential is None:
                raise ValueError("同步凭据不存在、已撤销或不属于当前工作空间")
        run = ContentMetricSyncRun(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id), platform=platform_key,
            credential_id=str(credential_id) if credential_id else None, requested_by=str(user_id),
            status="queued", payload_json={"items": items}, created_at=_utcnow(),
        )
        self.session.add(run)
        await self.session.flush()
        return self._dict(run)

    async def list(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, limit: int = 20) -> list[dict[str, Any]]:
        await self.content._workspace(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(select(ContentMetricSyncRun).where(
            ContentMetricSyncRun.workspace_id == str(workspace_id), ContentMetricSyncRun.tenant_id == str(tenant_id),
        ).order_by(ContentMetricSyncRun.created_at.desc()).limit(limit))
        return [self._dict(item) for item in result.scalars().all()]

    async def get(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> dict[str, Any] | None:
        run = await self.session.scalar(select(ContentMetricSyncRun).where(ContentMetricSyncRun.id == str(run_id), ContentMetricSyncRun.tenant_id == str(tenant_id)))
        if run is None:
            return None
        await self.content._workspace(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        return self._dict(run)

    async def retry(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> dict[str, Any] | None:
        """Reset a failed snapshot run while preserving its original payload."""
        run = await self.session.scalar(select(ContentMetricSyncRun).where(
            ContentMetricSyncRun.id == str(run_id), ContentMetricSyncRun.tenant_id == str(tenant_id),
        ))
        if run is None:
            return None
        await self.content._workspace(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        if run.status != "failed":
            raise ValueError("只有失败的同步任务可以重试")
        run.status = "retrying"
        run.inserted = 0
        run.skipped = 0
        run.error_message = None
        run.task_id = None
        run.started_at = None
        run.finished_at = None
        await self.session.flush()
        return self._dict(run)

    async def execute(self, *, run_id: str) -> dict[str, Any] | None:
        run = await self.session.scalar(select(ContentMetricSyncRun).where(ContentMetricSyncRun.id == str(run_id)))
        if run is None:
            return None
        if run.status not in {"queued", "retrying"}:
            return self._dict(run)
        run.status = "running"
        run.started_at = _utcnow()
        run.error_message = None
        await self.session.flush()
        try:
            raw_items = list((run.payload_json or {}).get("items") or [])
            if not raw_items:
                connector = ContentConnectorRegistry().get(str(run.platform))
                if connector is None or not hasattr(connector, "fetch_metrics"):
                    raise ValueError("该平台尚未注册真实指标连接器；请提交人工指标快照")
                if not run.credential_id:
                    raise ValueError("读取平台真实指标必须绑定连接凭据")
                resolved = await self.credentials.resolve(
                    credential_id=str(run.credential_id), workspace_id=str(run.workspace_id), tenant_id=str(run.tenant_id),
                )
                if resolved is None:
                    raise ValueError("同步凭据不存在、已撤销或不属于当前工作空间")
                _, credentials = resolved
                records = list((await self.session.execute(select(ContentPublishRecord).where(
                    ContentPublishRecord.workspace_id == str(run.workspace_id),
                    ContentPublishRecord.tenant_id == str(run.tenant_id),
                    ContentPublishRecord.platform == str(run.platform),
                    ContentPublishRecord.status == "published",
                    ContentPublishRecord.external_id.is_not(None),
                ).order_by(ContentPublishRecord.published_at.desc()).limit(100))).scalars().all())
                for record in records:
                    fetched = await connector.fetch_metrics(external_id=str(record.external_id), credentials=credentials)
                    if str(fetched.get("status")) != "configured":
                        raise ValueError(str(fetched.get("message") or "平台指标读取失败"))
                    collected_at = fetched.get("collected_at") or _utcnow().isoformat()
                    raw_items.append({"publish_id": record.id, "collected_at": collected_at, "metric": fetched.get("metric") or {}})
            items = []
            for item in raw_items:
                normalized = dict(item)
                collected_at = normalized.get("collected_at")
                if isinstance(collected_at, str):
                    normalized["collected_at"] = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
                items.append(normalized)
            result = await self.content.import_metrics(
                workspace_id=UUID(str(run.workspace_id)), tenant_id=UUID(str(run.tenant_id)),
                user_id=UUID(str(run.requested_by)), is_superuser=False, items=items,
            )
            run.inserted = int(result.get("inserted", 0))
            run.skipped = int(result.get("skipped", 0))
            run.status = "completed"
        except Exception as exc:  # worker records failure for UI retry/audit
            run.status = "failed"
            run.error_message = str(exc)[:1000]
        finally:
            run.finished_at = _utcnow()
            await self.session.flush()
        return self._dict(run)
