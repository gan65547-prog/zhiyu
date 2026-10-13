from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import Base, ContentConnectorCredential, ContentPublishRecord, ResearchReport, Tenant, User, Workspace, WorkspaceMember
from services.impl.content_service import ContentService
import services.impl.content_service as content_service_module
from services.impl.content_generation_service import ContentGenerationService
from services.impl.content_connector_registry import ContentConnectorRegistry, WebsiteWebhookPublisher, XPostPublisher
import services.impl.content_connector_registry as connector_module
from services.impl.content_publishing_service import ContentPublishingService
from services.impl.research_service import ResearchService


@pytest_asyncio.fixture
async def content_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _identity(session):
    tenant = Tenant(name="Content tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"content-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Content workspace")
    session.add_all([tenant, user, workspace]); await session.flush()
    session.add(WorkspaceMember(workspace=workspace, user=user)); await session.flush()
    return tenant, user, workspace


@pytest.mark.asyncio
async def test_content_topic_and_draft_review_are_workspace_scoped(content_session):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    topic = await service.create_topic(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "行业趋势选题", "brief": "从研究报告提炼内容"},
    )
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "topic_id": topic["id"], "title": "行业趋势初稿", "body": "草稿内容"},
    )
    updated = await service.update_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"title": "行业趋势修订稿", "body": "修订后的草稿内容"},
    )
    assert updated["title"] == "行业趋势修订稿"
    assert (await service.list_topics(workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False))[0]["id"] == topic["id"]
    reviewed = await service.review_draft(draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False, status="approved")
    assert reviewed["review_status"] == "approved"
    with pytest.raises(ValueError):
        await service.review_draft(draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False, status="rejected")
    with pytest.raises(ValueError, match="不能直接编辑"):
        await service.update_draft(
            draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
            is_superuser=False, data={"body": "不应修改"},
        )
    published = await service.publish_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"platform": "manual", "external_id": "post-1"},
    )
    assert published["platform"] == "manual"
    with pytest.raises(ValueError, match="需要先配置并绑定发布凭据"):
        await service.publish_draft(
            draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
            is_superuser=False, data={"platform": "website"},
        )
    measured = await service.add_metric(
        publish_id=UUID(str(published["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"impressions": 100, "likes": 8},
    )
    assert measured["latest_metrics"]["impressions"] == 100
    calendar = await service.list_publishes(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert len(calendar) == 1
    assert calendar[0]["latest_metrics"]["likes"] == 8
    retrospective = await service.create_retrospective(
        publish_id=UUID(str(published["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False,
    )
    assert retrospective["metric_snapshot"]["impressions"] == 100
    same_retrospective = await service.create_retrospective(
        publish_id=UUID(str(published["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False,
    )
    assert same_retrospective["id"] == retrospective["id"]


@pytest.mark.asyncio
async def test_pending_platform_adapters_cannot_be_published_or_scheduled(content_session):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "待适配平台", "body": "正文"},
    )
    await service.review_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, status="approved",
    )

    for platform in ("douyin", "zhihu"):
        with pytest.raises(ValueError, match="尚未注册发布连接器"):
            await service.publish_draft(
                draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
                is_superuser=False, data={"platform": platform},
            )
        with pytest.raises(ValueError, match="尚未注册发布连接器"):
            await service.schedule_draft(
                draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
                is_superuser=False,
                data={"platform": platform, "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1)},
            )


@pytest.mark.asyncio
async def test_registered_connector_publish_and_schedule_bind_workspace_credential(content_session):
    tenant, user, workspace = await _identity(content_session)
    credential = ContentConnectorCredential(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        platform="x",
        name="X 回归凭据",
        encrypted_credentials="encrypted-test-value",
        credential_hint="测试凭据",
        created_by=user.id,
    )
    content_session.add(credential)
    await content_session.flush()
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "凭据绑定闭环", "body": "正文"},
    )
    await service.review_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, status="approved",
    )

    published = await service.publish_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"platform": "x", "credential_id": credential.id},
    )
    scheduled = await service.schedule_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False,
        data={"platform": "x", "credential_id": credential.id, "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1)},
    )
    assert published["platform"] == "x"
    assert scheduled["platform"] == "x"
    published_record = await content_session.get(ContentPublishRecord, published["id"])
    scheduled_record = await content_session.get(ContentPublishRecord, scheduled["id"])
    assert published_record is not None and published_record.credential_id == credential.id
    assert scheduled_record is not None and scheduled_record.credential_id == credential.id


@pytest.mark.asyncio
async def test_metric_import_is_idempotent_and_workspace_scoped(content_session):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "指标导入", "body": "正文"},
    )
    await service.review_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, status="approved",
    )
    published = await service.publish_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"platform": "manual"},
    )
    collected_at = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
    imported = await service.import_metrics(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        items=[{"publish_id": published["id"], "collected_at": collected_at, "metric": {"impressions": 200, "clicks": 12}}],
    )
    duplicate_import = await service.import_metrics(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        items=[{"publish_id": published["id"], "collected_at": collected_at, "metric": {"impressions": 999}}],
    )
    assert imported == {"workspace_id": workspace.id, "inserted": 1, "skipped": 0}
    assert duplicate_import == {"workspace_id": workspace.id, "inserted": 0, "skipped": 1}


@pytest.mark.asyncio
async def test_draft_rewrite_keeps_canonical_content_and_is_idempotent(content_session):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "平台适配", "body": "第一段\n\n第二段"},
    )

    rewritten = await service.rewrite_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, platforms=["wechat", "x", "wechat"],
    )
    assert rewritten["title"] == "平台适配"
    assert rewritten["body"] == "第一段\n\n第二段"
    assert set(rewritten["metadata"]["platform_variants"]) == {"wechat", "x"}
    assert "欢迎转发" in rewritten["metadata"]["platform_variants"]["wechat"]

    same = await service.rewrite_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, platforms=["wechat"],
    )
    assert same["metadata"]["platform_variants"]["wechat"] == rewritten["metadata"]["platform_variants"]["wechat"]


@pytest.mark.asyncio
async def test_model_rewrite_keeps_canonical_content_and_separates_variant(content_session, monkeypatch):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "模型改写", "body": "原始正文"},
    )

    async def fake_rewrite_with_model(**_kwargs):
        return {"content": "模型版本", "platform": "wechat", "model": "test-model", "requires_human_review": True}

    monkeypatch.setattr(content_service_module, "rewrite_with_model", fake_rewrite_with_model)
    rewritten = await service.rewrite_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, platforms=["wechat"], mode="model", provider="openai", max_tokens=256,
    )

    assert rewritten["body"] == "原始正文"
    assert rewritten["metadata"]["platform_model_variants"]["wechat"]["content"] == "模型版本"
    assert rewritten["metadata"]["model_rewrite_requires_review"] is True


@pytest.mark.asyncio
async def test_approved_draft_can_be_scheduled_idempotently(content_session):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "可排期草稿", "body": "正文"},
    )
    await service.review_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, status="approved",
    )
    scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
    scheduled = await service.schedule_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"platform": "manual", "scheduled_at": scheduled_at},
    )
    duplicate = await service.schedule_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"platform": "manual", "scheduled_at": scheduled_at + timedelta(days=1)},
    )
    assert scheduled["status"] == "scheduled"
    assert scheduled["id"] == duplicate["id"]
    assert len(await service.list_publishes(workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False)) == 1


@pytest.mark.asyncio
async def test_due_manual_schedule_requires_confirmation_before_published(content_session):
    tenant, user, workspace = await _identity(content_session)
    service = ContentService(content_session)
    draft = await service.create_draft(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "title": "待执行排期", "body": "正文"},
    )
    await service.review_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, status="approved",
    )
    scheduled = await service.schedule_draft(
        draft_id=UUID(str(draft["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"platform": "manual", "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1)},
    )
    record = await content_session.get(ContentPublishRecord, scheduled["id"])
    record.published_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    await content_session.flush()

    assert await ContentPublishingService(content_session).dispatch_due_schedules() == 1
    assert record.status == "ready"
    confirmed = await service.confirm_publish(
        publish_id=record.id, tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, data={"external_id": "manual-1"},
    )
    assert confirmed["status"] == "published"
    assert confirmed["external_id"] == "manual-1"


def test_content_connector_registry_is_explicit_and_allowlisted():
    registry = ContentConnectorRegistry()
    assert [item["key"] for item in registry.describe()] == ["manual", "website", "x", "wechat", "douyin", "zhihu"]
    assert registry.get("manual") is not None
    assert registry.get("website") is not None
    assert registry.get("x") is not None
    assert registry.get("wechat") is not None
    assert registry.get("公众号") is None


@pytest.mark.asyncio
async def test_website_webhook_publisher_sends_reviewed_content_without_credentials(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "site-post-42"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr(connector_module.SafeFetcher, "_validate_url", AsyncMock(return_value=None))

    result = await WebsiteWebhookPublisher().dispatch(
        draft=SimpleNamespace(id="draft-1", title="审核后的标题", body="审核后的正文"),
        record=SimpleNamespace(id="publish-1"),
        credentials={"webhook_url": "https://publisher.example.test/hooks/content", "api_token": "must-not-leak"},
    )

    assert result.status == "published"
    assert result.external_id == "site-post-42"
    assert captured["url"] == "https://publisher.example.test/hooks/content"
    assert captured["json"]["draft"]["title"] == "审核后的标题"
    assert "api_token" not in captured["json"]


@pytest.mark.asyncio
async def test_x_publisher_posts_user_context_token_without_leaking_it(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"data": {"id": "x-post-42"}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    token = "oauth-user-token"
    result = await XPostPublisher().dispatch(
        draft=SimpleNamespace(id="draft-1", title="审核后的标题", body="审核后的正文"),
        record=SimpleNamespace(id="publish-1"),
        credentials={"access_token": token},
    )

    assert result.status == "published"
    assert result.external_id == "x-post-42"
    assert captured["url"] == "https://api.x.com/2/tweets"
    assert captured["headers"]["Authorization"] == f"Bearer {token}"
    assert captured["json"] == {"text": "审核后的标题\n\n审核后的正文"}
    assert token not in str(result.response)


@pytest.mark.asyncio
async def test_x_publisher_rejects_missing_or_oversized_credentials():
    publisher = XPostPublisher()
    missing = await publisher.dispatch(
        draft=SimpleNamespace(title="标题", body="正文"), record=SimpleNamespace(id="publish-1"), credentials={},
    )
    assert missing.status == "failed"
    assert missing.response["retryable"] is False

    oversized = await publisher.dispatch(
        draft=SimpleNamespace(title="x" * 281, body=""), record=SimpleNamespace(id="publish-1"), credentials={"access_token": "token"},
    )
    assert oversized.status == "failed"
    assert oversized.response["retryable"] is False


@pytest.mark.asyncio
async def test_x_publisher_retries_rate_limit(monkeypatch):
    class FakeResponse:
        status_code = 429

        def json(self):
            return {"title": "Too Many Requests"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            return FakeResponse()

    monkeypatch.setattr(connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = await XPostPublisher().dispatch(
        draft=SimpleNamespace(title="标题", body="正文"), record=SimpleNamespace(id="publish-1"), credentials={"access_token": "token"},
    )
    assert result.status == "failed"
    assert result.response["retryable"] is True


@pytest.mark.asyncio
async def test_x_publisher_fetches_public_metrics_without_leaking_token(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "data": {
                    "id": "123456789",
                    "created_at": "2026-08-10T02:00:00Z",
                    "public_metrics": {
                        "impression_count": 1200,
                        "like_count": 96,
                        "reply_count": 12,
                        "retweet_count": 18,
                        "quote_count": 4,
                    },
                },
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, *, headers, params):
            captured.update({"url": url, "headers": headers, "params": params})
            return FakeResponse()

    monkeypatch.setattr(connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    token = "metrics-oauth-token"
    result = await XPostPublisher().fetch_metrics(external_id="123456789", credentials={"access_token": token})

    assert result["status"] == "configured"
    assert result["metric"] == {
        "impressions": 1200,
        "clicks": 0,
        "likes": 96,
        "comments": 12,
        "shares": 22,
        "raw": {"source": "x_api_v2", "public_metrics": {
            "impression_count": 1200, "like_count": 96, "reply_count": 12,
            "retweet_count": 18, "quote_count": 4,
        }},
    }
    assert captured["url"] == "https://api.x.com/2/tweets/123456789"
    assert captured["params"] == {"tweet.fields": "public_metrics,created_at"}
    assert token not in str(result)


@pytest.mark.asyncio
async def test_approved_research_report_becomes_traceable_pending_draft(content_session):
    tenant, user, workspace = await _identity(content_session)
    project = await ResearchService(content_session).create_project(
        tenant_id=tenant.id,
        user_id=user.id,
        is_superuser=False,
        data={"workspace_id": workspace.id, "name": "内容转化研究", "questions": [{"question": "用户关注什么？"}]},
    )
    run = await ResearchService(content_session).create_run(
        project_id=UUID(str(project["id"])),
        tenant_id=tenant.id,
        user_id=user.id,
        is_superuser=False,
        limits={},
    )
    report = ResearchReport(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        run_id=run["id"],
        content_markdown="# 已审核结论\n\n行业正在加速采用 AI 工作台。",
        review_status="approved",
        citation_completeness=0.9,
    )
    content_session.add(report)
    await content_session.flush()

    draft = await ContentGenerationService(content_session).create_draft_from_report(
        report_id=report.id,
        tenant_id=tenant.id,
        user_id=user.id,
        is_superuser=False,
    )

    assert draft["review_status"] == "pending"
    assert draft["metadata"]["source_type"] == "research_report"
    assert draft["metadata"]["research_report_id"] == str(report.id)
    assert draft["metadata"]["requires_human_review"] is True
    assert str(report.id) in draft["body"]
    duplicate = await ContentGenerationService(content_session).create_draft_from_report(
        report_id=report.id,
        tenant_id=tenant.id,
        user_id=user.id,
        is_superuser=False,
    )
    assert duplicate["id"] == draft["id"]


@pytest.mark.asyncio
async def test_unapproved_research_report_cannot_become_draft(content_session):
    tenant, user, workspace = await _identity(content_session)
    project = await ResearchService(content_session).create_project(
        tenant_id=tenant.id,
        user_id=user.id,
        is_superuser=False,
        data={"workspace_id": workspace.id, "name": "待审核研究", "questions": [{"question": "结论？"}]},
    )
    run = await ResearchService(content_session).create_run(
        project_id=UUID(str(project["id"])),
        tenant_id=tenant.id,
        user_id=user.id,
        is_superuser=False,
        limits={},
    )
    report = ResearchReport(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        run_id=run["id"],
        content_markdown="# 待审核报告",
        review_status="draft",
    )
    content_session.add(report)
    await content_session.flush()

    with pytest.raises(ValueError, match="审核通过"):
        await ContentGenerationService(content_session).create_draft_from_report(
            report_id=report.id,
            tenant_id=tenant.id,
            user_id=user.id,
            is_superuser=False,
        )
