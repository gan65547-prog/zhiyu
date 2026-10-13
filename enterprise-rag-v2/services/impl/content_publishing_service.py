"""内容排期执行编排；外部平台只能通过白名单连接器接入。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import ContentDraft, ContentPublishRecord
from services.impl.content_connector_registry import ContentConnectorRegistry
from services.impl.content_credential_service import ContentCredentialService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentPublishingService:
    """执行到期排期，不把排期记录直接当成外部发布成功。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry = ContentConnectorRegistry()
        self.credentials = ContentCredentialService(session)

    def list_connectors(self) -> list[dict[str, Any]]:
        return self.registry.describe()

    async def dispatch_due_schedules(self, *, limit: int = 50) -> int:
        result = await self.session.execute(
            select(ContentPublishRecord).where(
                ContentPublishRecord.status == "scheduled",
                ContentPublishRecord.published_at <= _utcnow(),
            ).order_by(ContentPublishRecord.published_at.asc()).with_for_update(skip_locked=True).limit(limit)
        )
        records = list(result.scalars().all())
        for record in records:
            await self._dispatch_one(record)
        await self.session.flush()
        return len(records)

    async def _dispatch_one(self, record: ContentPublishRecord) -> None:
        draft = await self.session.get(ContentDraft, str(record.draft_id))
        if draft is None or draft.review_status != "approved":
            record.status = "failed"
            record.response_json = {"error": "草稿不存在或未保持审核通过", "retryable": False}
            return
        connector = self.registry.get(record.platform)
        if connector is not None:
            resolved = None
            if record.credential_id:
                resolved = await self.credentials.resolve(credential_id=str(record.credential_id), workspace_id=str(record.workspace_id), tenant_id=str(record.tenant_id))
                if resolved is None:
                    record.status = "failed"
                    record.response_json = {"error": "发布凭据不存在、已禁用或不属于当前工作空间", "retryable": False}
                    return
                resolved[0].last_used_at = _utcnow()
            result = await connector.dispatch(draft=draft, record=record, credentials=resolved[1] if resolved else None)
            record.status = result.status
            record.external_id = result.external_id
            record.response_json = result.response
            return
        record.status = "failed"
        record.response_json = {"error": f"未注册内容发布连接器: {record.platform}", "retryable": False}


def publishing_result(record: ContentPublishRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "draft_id": record.draft_id,
        "workspace_id": record.workspace_id,
        "platform": record.platform,
        "status": record.status,
        "external_id": record.external_id,
        "published_at": record.published_at,
        "latest_metrics": None,
    }
