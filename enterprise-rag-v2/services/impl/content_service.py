"""内容中心应用服务：选题、草稿和审核，不负责外部平台发布。"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import ContentDraft, ContentMetric, ContentPublishRecord, ContentRetrospective, ContentTopic
from services.impl.asset_service import AssetServiceImpl
from services.impl.content_publishing_service import publishing_result
from services.impl.content_connector_registry import ContentConnectorRegistry
from services.impl.content_rewrite_service import rewrite_for_platform, rewrite_with_model
from services.impl.user_llm_runtime import resolve_user_llm_runtime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AssetServiceImpl(session)

    async def _workspace(self, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> None:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)

    @staticmethod
    def _topic_dict(item: ContentTopic) -> dict[str, Any]:
        return {"id": item.id, "workspace_id": item.workspace_id, "created_by": item.created_by, "title": item.title, "brief": item.brief, "status": item.status, "tags": list(item.tags or []), "created_at": item.created_at, "updated_at": item.updated_at}

    @staticmethod
    def _draft_dict(item: ContentDraft) -> dict[str, Any]:
        return {"id": item.id, "workspace_id": item.workspace_id, "topic_id": item.topic_id, "created_by": item.created_by, "title": item.title, "body": item.body, "status": item.status, "review_status": item.review_status, "reviewer_id": item.reviewer_id, "reviewed_at": item.reviewed_at, "metadata": dict(item.metadata_json or {}), "created_at": item.created_at, "updated_at": item.updated_at}

    async def create_topic(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> dict[str, Any]:
        workspace_id = UUID(str(data["workspace_id"]))
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        item = ContentTopic(tenant_id=str(tenant_id), workspace_id=str(workspace_id), created_by=str(user_id), title=str(data["title"]).strip(), brief=data.get("brief"), status="idea", tags=data.get("tags") or [], created_at=_utcnow(), updated_at=_utcnow())
        self.session.add(item); await self.session.flush()
        return self._topic_dict(item)

    async def list_topics(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> list[dict[str, Any]]:
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(select(ContentTopic).where(ContentTopic.workspace_id == str(workspace_id), ContentTopic.tenant_id == str(tenant_id)).order_by(ContentTopic.created_at.desc()))
        return [self._topic_dict(item) for item in result.scalars().all()]

    async def create_draft(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> dict[str, Any]:
        workspace_id = UUID(str(data["workspace_id"]))
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        if data.get("topic_id") and await self.session.scalar(select(ContentTopic.id).where(ContentTopic.id == str(data["topic_id"]), ContentTopic.workspace_id == str(workspace_id), ContentTopic.tenant_id == str(tenant_id))) is None:
            raise ValueError("选题不存在或不属于当前工作空间")
        item = ContentDraft(tenant_id=str(tenant_id), workspace_id=str(workspace_id), topic_id=str(data["topic_id"]) if data.get("topic_id") else None, created_by=str(user_id), title=str(data["title"]).strip(), body=data.get("body") or "", status="draft", review_status="pending", metadata_json=data.get("metadata") or {}, created_at=_utcnow(), updated_at=_utcnow())
        self.session.add(item); await self.session.flush()
        return self._draft_dict(item)

    async def update_draft(self, *, draft_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        item = await self.session.scalar(select(ContentDraft).where(ContentDraft.id == str(draft_id), ContentDraft.tenant_id == str(tenant_id)))
        if item is None: return None
        await self._workspace(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        if item.review_status == "approved": raise ValueError("审核通过的草稿不能直接编辑")
        if "topic_id" in data and data["topic_id"]:
            topic = await self.session.scalar(select(ContentTopic.id).where(ContentTopic.id == str(data["topic_id"]), ContentTopic.workspace_id == item.workspace_id, ContentTopic.tenant_id == str(tenant_id)))
            if topic is None: raise ValueError("选题不存在或不属于当前工作空间")
            item.topic_id = str(data["topic_id"])
        elif "topic_id" in data:
            item.topic_id = None
        if data.get("title") is not None: item.title = str(data["title"]).strip()
        if data.get("body") is not None: item.body = str(data["body"])
        if data.get("metadata") is not None: item.metadata_json = data["metadata"]
        if item.review_status == "rejected":
            item.review_status, item.reviewer_id, item.reviewed_at = "pending", None, None
        item.updated_at = _utcnow()
        await self.session.flush()
        return self._draft_dict(item)

    async def rewrite_draft(self, *, draft_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, platforms: list[str], mode: str = "deterministic", provider: Optional[str] = None, max_tokens: int = 1200) -> Optional[dict[str, Any]]:
        item = await self.session.scalar(select(ContentDraft).where(ContentDraft.id == str(draft_id), ContentDraft.tenant_id == str(tenant_id)))
        if item is None:
            return None
        await self._workspace(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        if not item.body.strip():
            raise ValueError("空草稿不能进行平台改写")
        metadata = dict(item.metadata_json or {})
        if mode not in {"deterministic", "model"}:
            raise ValueError("改写模式必须是 deterministic 或 model")
        if mode == "model":
            runtime = await resolve_user_llm_runtime(self.session, str(user_id))
            variants = dict(metadata.get("platform_model_variants") or {})
            for platform in dict.fromkeys(platforms):
                variants[platform.strip().lower()] = await rewrite_with_model(
                    title=item.title, body=item.body, platform=platform,
                    provider=provider or runtime.get("provider"), max_tokens=max_tokens,
                    api_key=runtime.get("api_key"), base_url=runtime.get("base_url"), model=runtime.get("model"),
                )
            metadata["platform_model_variants"] = variants
            metadata["model_rewrite_requires_review"] = True
        else:
            variants = dict(metadata.get("platform_variants") or {})
            for platform in dict.fromkeys(platforms):
                variants[platform.strip().lower()] = rewrite_for_platform(item.title, item.body, platform)
            metadata["platform_variants"] = variants
        item.metadata_json = metadata
        item.updated_at = _utcnow()
        await self.session.flush()
        return self._draft_dict(item)

    async def list_drafts(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, review_status: Optional[str] = None) -> list[dict[str, Any]]:
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [ContentDraft.workspace_id == str(workspace_id), ContentDraft.tenant_id == str(tenant_id)]
        if review_status: conditions.append(ContentDraft.review_status == review_status)
        result = await self.session.execute(select(ContentDraft).where(*conditions).order_by(ContentDraft.created_at.desc()))
        return [self._draft_dict(item) for item in result.scalars().all()]

    async def review_draft(self, *, draft_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, status: str) -> Optional[dict[str, Any]]:
        if status not in {"approved", "rejected"}: raise ValueError("审核状态必须是 approved 或 rejected")
        item = await self.session.scalar(select(ContentDraft).where(ContentDraft.id == str(draft_id), ContentDraft.tenant_id == str(tenant_id)))
        if item is None: return None
        await self._workspace(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        if item.review_status != "pending": raise ValueError("草稿已经审核，不能重复操作")
        item.review_status, item.reviewer_id, item.reviewed_at = status, str(user_id), _utcnow()
        await self.session.flush()
        return self._draft_dict(item)

    async def publish_draft(self, *, draft_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        draft = await self.session.scalar(select(ContentDraft).where(ContentDraft.id == str(draft_id), ContentDraft.tenant_id == str(tenant_id)))
        if draft is None: return None
        await self._workspace(UUID(str(draft.workspace_id)), tenant_id, user_id, is_superuser)
        if draft.review_status != "approved": raise ValueError("只有审核通过的草稿才能记录发布")
        platform = str(data["platform"]).strip().lower()
        if ContentConnectorRegistry().get(platform) is None:
            raise ValueError(f"平台“{platform}”尚未注册发布连接器，请选择人工发布或先完成平台适配")
        credential_id = data.get("credential_id")
        connector = ContentConnectorRegistry().get(platform)
        if getattr(connector, "requires_credentials", False) and not credential_id:
            raise ValueError(f"平台“{platform}”需要先配置并绑定发布凭据")
        if credential_id:
            from infrastructure.database.models import ContentConnectorCredential
            credential = await self.session.scalar(select(ContentConnectorCredential.id).where(ContentConnectorCredential.id == str(credential_id), ContentConnectorCredential.workspace_id == draft.workspace_id, ContentConnectorCredential.tenant_id == str(tenant_id), ContentConnectorCredential.status == "active"))
            if credential is None: raise ValueError("发布凭据不存在、已禁用或不属于当前工作空间")
        record = ContentPublishRecord(tenant_id=str(tenant_id), workspace_id=draft.workspace_id, draft_id=draft.id, platform=platform, credential_id=str(credential_id) if credential_id else None, status="ready", external_id=data.get("external_id"), response_json={"requires_manual_confirmation": True, **(data.get("response") or {})}, published_at=_utcnow(), created_at=_utcnow())
        self.session.add(record); await self.session.flush()
        return {"id": record.id, "draft_id": record.draft_id, "workspace_id": record.workspace_id, "platform": record.platform, "status": record.status, "external_id": record.external_id, "published_at": record.published_at, "latest_metrics": None}

    async def schedule_draft(self, *, draft_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        draft = await self.session.scalar(select(ContentDraft).where(ContentDraft.id == str(draft_id), ContentDraft.tenant_id == str(tenant_id)))
        if draft is None: return None
        await self._workspace(UUID(str(draft.workspace_id)), tenant_id, user_id, is_superuser)
        if draft.review_status != "approved": raise ValueError("只有审核通过的草稿才能排期")
        scheduled_at = data["scheduled_at"]
        if scheduled_at.tzinfo:
            scheduled_at = scheduled_at.astimezone(timezone.utc)
        if scheduled_at <= _utcnow(): raise ValueError("排期时间必须晚于当前时间")
        platform = str(data["platform"]).strip().lower()
        if ContentConnectorRegistry().get(platform) is None:
            raise ValueError(f"平台“{platform}”尚未注册发布连接器，请选择人工发布或先完成平台适配")
        connector = ContentConnectorRegistry().get(platform)
        if getattr(connector, "requires_credentials", False) and not data.get("credential_id"):
            raise ValueError(f"平台“{platform}”需要先配置并绑定发布凭据")
        existing = await self.session.scalar(select(ContentPublishRecord).where(ContentPublishRecord.draft_id == draft.id, ContentPublishRecord.platform == platform, ContentPublishRecord.status == "scheduled").order_by(ContentPublishRecord.created_at.asc()))
        if existing is not None: return {"id": existing.id, "draft_id": existing.draft_id, "workspace_id": existing.workspace_id, "platform": existing.platform, "status": existing.status, "external_id": existing.external_id, "published_at": existing.published_at, "latest_metrics": None}
        credential_id = data.get("credential_id")
        if credential_id:
            from infrastructure.database.models import ContentConnectorCredential
            credential = await self.session.scalar(select(ContentConnectorCredential.id).where(ContentConnectorCredential.id == str(credential_id), ContentConnectorCredential.workspace_id == draft.workspace_id, ContentConnectorCredential.tenant_id == str(tenant_id), ContentConnectorCredential.status == "active"))
            if credential is None: raise ValueError("发布凭据不存在、已禁用或不属于当前工作空间")
        record = ContentPublishRecord(tenant_id=str(tenant_id), workspace_id=draft.workspace_id, draft_id=draft.id, platform=platform, credential_id=str(credential_id) if credential_id else None, status="scheduled", published_at=scheduled_at, created_at=_utcnow())
        self.session.add(record); await self.session.flush()
        return {"id": record.id, "draft_id": record.draft_id, "workspace_id": record.workspace_id, "platform": record.platform, "status": record.status, "external_id": None, "published_at": record.published_at, "latest_metrics": None}

    async def confirm_publish(self, *, publish_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        record = await self.session.scalar(select(ContentPublishRecord).where(ContentPublishRecord.id == str(publish_id), ContentPublishRecord.tenant_id == str(tenant_id)))
        if record is None: return None
        await self._workspace(UUID(str(record.workspace_id)), tenant_id, user_id, is_superuser)
        if record.status not in {"scheduled", "ready"}: raise ValueError("只有待发布或待手动确认的记录才能确认发布")
        record.status = "published"
        record.external_id = data.get("external_id")
        record.response_json = data.get("response") or record.response_json or {}
        await self.session.flush()
        return publishing_result(record)

    async def list_publishes(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> list[dict[str, Any]]:
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [ContentPublishRecord.workspace_id == str(workspace_id), ContentPublishRecord.tenant_id == str(tenant_id)]
        if from_date:
            conditions.append(ContentPublishRecord.published_at >= from_date)
        if to_date:
            conditions.append(ContentPublishRecord.published_at <= to_date)
        result = await self.session.execute(select(ContentPublishRecord).where(*conditions).order_by(ContentPublishRecord.published_at.desc()))
        items = []
        for record in result.scalars().all():
            metric = await self.session.scalar(select(ContentMetric).where(ContentMetric.publish_record_id == str(record.id)).order_by(ContentMetric.collected_at.desc()).limit(1))
            items.append({"id": record.id, "draft_id": record.draft_id, "workspace_id": record.workspace_id, "platform": record.platform, "status": record.status, "external_id": record.external_id, "published_at": record.published_at, "latest_metrics": {"impressions": metric.impressions, "clicks": metric.clicks, "likes": metric.likes, "comments": metric.comments, "shares": metric.shares, "collected_at": metric.collected_at} if metric else None})
        return items

    async def list_metrics(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, limit: int = 500) -> list[dict[str, Any]]:
        """返回工作空间的历史指标快照，供平台趋势和内容表现分析使用。"""
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(
            select(ContentMetric, ContentPublishRecord)
            .join(ContentPublishRecord, ContentPublishRecord.id == ContentMetric.publish_record_id)
            .where(ContentMetric.workspace_id == str(workspace_id), ContentMetric.tenant_id == str(tenant_id))
            .order_by(ContentMetric.collected_at.desc())
            .limit(max(1, min(limit, 1000)))
        )
        return [
            {
                "id": metric.id,
                "publish_record_id": metric.publish_record_id,
                "workspace_id": metric.workspace_id,
                "platform": record.platform,
                "published_at": record.published_at,
                "collected_at": metric.collected_at,
                "impressions": metric.impressions,
                "clicks": metric.clicks,
                "likes": metric.likes,
                "comments": metric.comments,
                "shares": metric.shares,
            }
            for metric, record in result.all()
        ]

    async def add_metric(self, *, publish_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        record = await self.session.scalar(select(ContentPublishRecord).where(ContentPublishRecord.id == str(publish_id), ContentPublishRecord.tenant_id == str(tenant_id)))
        if record is None: return None
        await self._workspace(UUID(str(record.workspace_id)), tenant_id, user_id, is_superuser)
        metric = ContentMetric(tenant_id=str(tenant_id), workspace_id=record.workspace_id, publish_record_id=record.id, impressions=int(data.get("impressions", 0)), clicks=int(data.get("clicks", 0)), likes=int(data.get("likes", 0)), comments=int(data.get("comments", 0)), shares=int(data.get("shares", 0)), raw_json=data.get("raw") or {}, collected_at=_utcnow())
        self.session.add(metric); await self.session.flush()
        return {"id": record.id, "draft_id": record.draft_id, "workspace_id": record.workspace_id, "platform": record.platform, "status": record.status, "external_id": record.external_id, "published_at": record.published_at, "latest_metrics": {"impressions": metric.impressions, "clicks": metric.clicks, "likes": metric.likes, "comments": metric.comments, "shares": metric.shares, "collected_at": metric.collected_at}}

    async def import_metrics(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, items: list[dict[str, Any]]) -> dict[str, Any]:
        """批量导入带采集时间的指标快照；同一发布记录和时间戳重复导入安全跳过。"""
        await self._workspace(workspace_id, tenant_id, user_id, is_superuser)
        inserted = 0
        skipped = 0
        for item in items:
            record = await self.session.scalar(select(ContentPublishRecord).where(
                ContentPublishRecord.id == str(item["publish_id"]),
                ContentPublishRecord.workspace_id == str(workspace_id),
                ContentPublishRecord.tenant_id == str(tenant_id),
            ))
            if record is None:
                raise ValueError("指标中的发布记录不存在或不属于当前工作空间")
            collected_at = item["collected_at"]
            if collected_at.tzinfo:
                collected_at = collected_at.astimezone(timezone.utc)
            existing = await self.session.scalar(select(ContentMetric.id).where(
                ContentMetric.publish_record_id == str(record.id), ContentMetric.collected_at == collected_at,
            ))
            if existing is not None:
                skipped += 1
                continue
            metric = item["metric"]
            self.session.add(ContentMetric(
                tenant_id=str(tenant_id), workspace_id=str(workspace_id), publish_record_id=record.id,
                impressions=int(metric.get("impressions", 0)), clicks=int(metric.get("clicks", 0)),
                likes=int(metric.get("likes", 0)), comments=int(metric.get("comments", 0)),
                shares=int(metric.get("shares", 0)), raw_json=metric.get("raw") or {}, collected_at=collected_at,
            ))
            inserted += 1
        await self.session.flush()
        return {"workspace_id": workspace_id, "inserted": inserted, "skipped": skipped}

    async def create_retrospective(self, *, publish_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        record = await self.session.scalar(select(ContentPublishRecord).where(ContentPublishRecord.id == str(publish_id), ContentPublishRecord.tenant_id == str(tenant_id)))
        if record is None: return None
        await self._workspace(UUID(str(record.workspace_id)), tenant_id, user_id, is_superuser)
        existing = await self.session.scalar(select(ContentRetrospective).where(ContentRetrospective.publish_record_id == record.id).order_by(ContentRetrospective.created_at.desc()).limit(1))
        if existing is not None: return self._retrospective_dict(existing)
        metric = await self.session.scalar(select(ContentMetric).where(ContentMetric.publish_record_id == str(record.id)).order_by(ContentMetric.collected_at.desc()).limit(1))
        if metric is None: raise ValueError("尚无内容指标，无法复盘")
        impressions = metric.impressions
        ctr = round(metric.clicks / impressions, 4) if impressions else 0.0
        engagement = round((metric.likes + metric.comments + metric.shares) / impressions, 4) if impressions else 0.0
        recommendations = []
        if not impressions: recommendations.append("补充曝光数据后再判断内容表现")
        elif ctr < 0.02: recommendations.append("优化标题和首屏信息，提升点击率")
        if engagement < 0.01: recommendations.append("增加明确问题或行动号召，促进互动")
        if not recommendations: recommendations.append("保留当前主题结构，尝试复用到相邻选题")
        snapshot = {"impressions": impressions, "clicks": metric.clicks, "likes": metric.likes, "comments": metric.comments, "shares": metric.shares, "ctr": ctr, "engagement_rate": engagement}
        summary = f"本次内容获得 {impressions} 次曝光，点击率 {ctr:.2%}，互动率 {engagement:.2%}。"
        retro = ContentRetrospective(tenant_id=str(tenant_id), workspace_id=record.workspace_id, publish_record_id=record.id, summary=summary, recommendations=recommendations, metric_snapshot=snapshot, created_by=str(user_id), created_at=_utcnow())
        self.session.add(retro); await self.session.flush()
        return self._retrospective_dict(retro)

    async def get_retrospective(self, *, publish_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        record = await self.session.scalar(select(ContentPublishRecord).where(ContentPublishRecord.id == str(publish_id), ContentPublishRecord.tenant_id == str(tenant_id)))
        if record is None: return None
        await self._workspace(UUID(str(record.workspace_id)), tenant_id, user_id, is_superuser)
        retro = await self.session.scalar(select(ContentRetrospective).where(ContentRetrospective.publish_record_id == record.id).order_by(ContentRetrospective.created_at.desc()).limit(1))
        return self._retrospective_dict(retro) if retro else None

    @staticmethod
    def _retrospective_dict(item: ContentRetrospective) -> dict[str, Any]:
        return {"id": item.id, "publish_record_id": item.publish_record_id, "workspace_id": item.workspace_id, "summary": item.summary, "recommendations": list(item.recommendations or []), "metric_snapshot": dict(item.metric_snapshot or {}), "created_by": item.created_by, "created_at": item.created_at}
