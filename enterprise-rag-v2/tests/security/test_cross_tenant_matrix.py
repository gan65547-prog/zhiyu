"""WB-05 跨租户越权测试矩阵（go-live 方案 C-05 节，release 2.2.0）。

矩阵：租户 A 的资源 × 两类未授权访问者，全部走真实服务层（真实 SQLite 会话，非 mock）：

- ``cross_tenant_b``：租户 B 的用户。按 ID 的资源入口先做租户过滤，
  期望 404 语义（服务层返回 ``None`` / ``False`` 或抛 ``LookupError``）；
- ``non_member_c``：租户 A 内、但不是工作空间 WA 成员的用户。
  期望 403 语义（抛内建 ``PermissionError``）。

异常/返回值与 API 层映射关系（依据 api/routers/*.py 的真实处理序列）：
- ``None`` / ``False`` / ``LookupError`` → HTTP 404；
- ``PermissionError`` → HTTP 403；
- 服务层若意外成功返回数据，即为越权漏洞，测试直接失败。
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import (
    Asset,
    Base,
    ContentDraft,
    ContentPublishRecord,
    Dataset,
    Document,
    DocumentType,
    KnowledgeItem,
    KnowledgeItemVersion,
    ResearchEvidence,
    ResearchProject,
    ResearchReport,
    ResearchRun,
    ResearchSource,
    Tenant,
    User,
    Workspace,
    WorkspaceMember,
)
from services.impl.asset_ingestion_service import AssetIngestionService
from services.impl.asset_service import AssetServiceImpl
from services.impl.content_service import ContentService
from services.impl.dataset_service import DatasetServiceImpl
from services.impl.document_service import DocumentServiceImpl
from services.impl.knowledge_service import KnowledgeService
from services.impl.research_service import ResearchService
from services.impl.workbench_service import WorkbenchService

# (身份标记, 按 ID 资源入口的期望语义)：跨租户 B → 404 语义；非成员 C → 403 语义。
ACTORS = (
    ("cross_tenant_b", "not_found"),
    ("non_member_c", "forbidden"),
)

ACTOR_IDS = [actor[0] for actor in ACTORS]


async def expect_rejection(call, *, expected: str) -> None:
    """执行一次服务调用并断言未授权访问被正确拒绝。

    expected="not_found"：允许 None / False / LookupError（API 404 语义）；
    expected="forbidden"：必须抛 PermissionError（API 403 语义）。
    任何意外成功或其它异常均视为断言失败（疑似越权漏洞）。
    """
    try:
        result = await call()
    except LookupError as exc:
        assert expected == "not_found", f"意外 LookupError（应为 403 语义）: {exc}"
        return
    except PermissionError as exc:
        assert expected == "forbidden", f"意外 PermissionError（应为 404 语义）: {exc}"
        return
    if expected == "forbidden":
        pytest.fail(f"预期 PermissionError（403），实际调用成功返回 {result!r} —— 疑似越权漏洞")
    assert result is None or result is False, (
        f"预期 404 语义（None/False），实际返回 {result!r} —— 疑似越权漏洞"
    )


@pytest_asyncio.fixture
async def matrix(tmp_path):
    """构建租户 A（含六类资源）、租户 B 用户、同租户非成员用户 C 的真实数据库。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cross_tenant.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # ---- 租户 A：owner 的工作空间 WA + 非成员用户 C 自己的工作空间 WC ----
        tenant_a = Tenant(name="Tenant A", contact_email=f"{uuid4()}@example.com")
        owner_a = User(tenant=tenant_a, username=f"owner-a-{uuid4().hex[:8]}", email=f"{uuid4()}@example.com", hashed_password="hash")
        ws_a = Workspace(tenant=tenant_a, name="Workspace A")
        user_c = User(tenant=tenant_a, username=f"user-c-{uuid4().hex[:8]}", email=f"{uuid4()}@example.com", hashed_password="hash")
        ws_c = Workspace(tenant=tenant_a, name="Workspace C")
        session.add_all([tenant_a, owner_a, ws_a, user_c, ws_c])
        await session.flush()
        session.add_all([
            WorkspaceMember(workspace=ws_a, user=owner_a),
            WorkspaceMember(workspace=ws_c, user=user_c),
        ])

        # ---- 租户 B：用户 B + 自己的工作空间 WB + 诱饵资源（用于隔离断言） ----
        tenant_b = Tenant(name="Tenant B", contact_email=f"{uuid4()}@example.com")
        user_b = User(tenant=tenant_b, username=f"user-b-{uuid4().hex[:8]}", email=f"{uuid4()}@example.com", hashed_password="hash")
        ws_b = Workspace(tenant=tenant_b, name="Workspace B")
        session.add_all([tenant_b, user_b, ws_b])
        await session.flush()
        session.add(WorkspaceMember(workspace=ws_b, user=user_b))
        decoy_b = Asset(tenant_id=tenant_b.id, workspace_id=ws_b.id, created_by=user_b.id, source_type="text", title="decoy-task-B", status="pending")
        decoy_c = Asset(tenant_id=tenant_a.id, workspace_id=ws_c.id, created_by=user_c.id, source_type="text", title="decoy-task-C", status="pending")
        session.add_all([decoy_b, decoy_c])

        # ---- 租户 A / 工作空间 WA 内的六类资源 ----
        asset = Asset(tenant_id=tenant_a.id, workspace_id=ws_a.id, created_by=owner_a.id, source_type="text", title="secret-asset-A", status="ready")
        session.add(asset)
        await session.flush()

        knowledge = KnowledgeItem(tenant_id=tenant_a.id, workspace_id=ws_a.id, created_by=owner_a.id, title="secret-knowledge-A", review_status="draft")
        session.add(knowledge)
        await session.flush()
        version = KnowledgeItemVersion(
            tenant_id=tenant_a.id, workspace_id=ws_a.id, knowledge_item_id=knowledge.id,
            version=1, title="v1-title", item_type="concept", definition="definition-A",
            created_by=owner_a.id,
        )
        session.add(version)

        project = ResearchProject(tenant_id=tenant_a.id, workspace_id=ws_a.id, created_by=owner_a.id, name="secret-research-A")
        session.add(project)
        await session.flush()
        run = ResearchRun(tenant_id=tenant_a.id, workspace_id=ws_a.id, project_id=project.id, created_by=owner_a.id, status="completed")
        session.add(run)
        await session.flush()
        source = ResearchSource(tenant_id=tenant_a.id, workspace_id=ws_a.id, run_id=run.id, title="source-A")
        session.add(source)
        await session.flush()
        evidence = ResearchEvidence(tenant_id=tenant_a.id, workspace_id=ws_a.id, run_id=run.id, source_id=source.id, quote="quote-A")
        report = ResearchReport(tenant_id=tenant_a.id, workspace_id=ws_a.id, run_id=run.id, content_markdown="report-A")
        draft = ContentDraft(tenant_id=tenant_a.id, workspace_id=ws_a.id, created_by=owner_a.id, title="secret-draft-A", body="body-A", review_status="pending")
        session.add_all([evidence, report, draft])
        await session.flush()
        publish = ContentPublishRecord(tenant_id=tenant_a.id, workspace_id=ws_a.id, draft_id=draft.id, platform="wechat", status="published")
        dataset = Dataset(workspace_id=ws_a.id, name="secret-dataset-A", embedding_model="test-embedding")
        session.add_all([publish, dataset])
        await session.flush()
        document = Document(dataset_id=dataset.id, file_name="secret-doc-A.txt", file_type=DocumentType.TXT, file_size=16, file_path="/tmp/secret-doc-A.txt")
        session.add(document)
        await session.commit()

        ids = {
            "tenant_a": tenant_a.id, "tenant_b": tenant_b.id,
            "owner_a": owner_a.id, "user_b": user_b.id, "user_c": user_c.id,
            "ws_a": ws_a.id, "ws_b": ws_b.id, "ws_c": ws_c.id,
            "asset": asset.id, "knowledge": knowledge.id, "version": version.id,
            "project": project.id, "run": run.id, "draft": draft.id, "publish": publish.id,
            "dataset": dataset.id, "document": document.id,
            "decoy_b": decoy_b.id, "decoy_c": decoy_c.id,
        }

    try:
        yield factory, ids
    finally:
        await engine.dispose()


def _actor_ids(ids: dict, actor_id: str) -> tuple[str, str]:
    """返回该身份的 (tenant_id, user_id)：C 用租户 A 但不在 WA 内。"""
    if actor_id == "non_member_c":
        return ids["tenant_a"], ids["user_c"]
    return ids["tenant_b"], ids["user_b"]


# ---------------------------------------------------------------------------
# 1. 素材（asset）：GET / PATCH（写路径）/ DELETE / organize / retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id, expected", ACTORS, ids=ACTOR_IDS)
async def test_01_asset_endpoints_reject_foreign_access(matrix, actor_id, expected):
    factory, ids = matrix
    tenant_id, user_id = _actor_ids(ids, actor_id)
    asset_id = ids["asset"]
    async with factory() as session:
        service = AssetServiceImpl(session)
        ingestion = AssetIngestionService(session)

        # GET /assets/{asset_id}
        await expect_rejection(
            lambda: service.get_asset(asset_id=asset_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # PATCH 等价写路径：素材无独立 PATCH 端点，POST /assets/{id}/text 与 /upload
        # 的底层实现是 AssetIngestionService.ingest_bytes（最贴近真实的编辑入口）。
        await expect_rejection(
            lambda: ingestion.ingest_bytes(
                asset_id=asset_id, tenant_id=tenant_id, user_id=user_id,
                content=b"payload", content_type="text/plain", is_superuser=False,
            ),
            expected=expected,
        )
        # DELETE /assets/{asset_id}
        await expect_rejection(
            lambda: service.delete_asset(asset_id=asset_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # POST /assets/{asset_id}/organize：路由守卫序列即先 get_asset（None→404 / PermissionError→403）
        await expect_rejection(
            lambda: service.get_asset(asset_id=asset_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # POST /assets/{asset_id}/retry
        await expect_rejection(
            lambda: service.prepare_retry(asset_id=asset_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )


# ---------------------------------------------------------------------------
# 2. 知识卡片：审核 / 版本回滚 / 读取 / 编辑 / 版本列表
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id, expected", ACTORS, ids=ACTOR_IDS)
async def test_02_knowledge_item_endpoints_reject_foreign_access(matrix, actor_id, expected):
    factory, ids = matrix
    tenant_id, user_id = _actor_ids(ids, actor_id)
    item_id, version_id = ids["knowledge"], ids["version"]
    async with factory() as session:
        service = KnowledgeService(session)

        # GET /knowledge/{item_id}
        await expect_rejection(
            lambda: service.get_item(item_id=item_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # PATCH /knowledge/{item_id}
        await expect_rejection(
            lambda: service.update_item(item_id=item_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False, changes={"title": "hacked"}),
            expected=expected,
        )
        # POST /knowledge/{item_id}/review（approve）
        await expect_rejection(
            lambda: service.review_item(item_id=item_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False, review_status="approved"),
            expected=expected,
        )
        # POST /knowledge/{item_id}/rollback
        await expect_rejection(
            lambda: service.rollback_item(item_id=item_id, version_id=version_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # GET /knowledge/{item_id}/versions
        await expect_rejection(
            lambda: service.list_versions(item_id=item_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )


# ---------------------------------------------------------------------------
# 3. 研究：项目运行列表 / 运行读取 / 取消 / 重试 / 报告 / 证据 / 结论
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id, expected", ACTORS, ids=ACTOR_IDS)
async def test_03_research_endpoints_reject_foreign_access(matrix, actor_id, expected):
    factory, ids = matrix
    tenant_id, user_id = _actor_ids(ids, actor_id)
    project_id, run_id = ids["project"], ids["run"]
    async with factory() as session:
        service = ResearchService(session)

        # GET /research/projects/{project_id}/runs
        await expect_rejection(
            lambda: service.list_runs(project_id=project_id, tenant_id=tenant_id, user_id=user_id, page=1, page_size=20, is_superuser=False),
            expected=expected,
        )
        # GET /research/runs/{run_id}
        await expect_rejection(
            lambda: service.get_run(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # POST /research/runs/{run_id}/cancel
        await expect_rejection(
            lambda: service.cancel_run(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # POST /research/runs/{run_id}/retry
        await expect_rejection(
            lambda: service.retry_run(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # GET /research/runs/{run_id}/report
        await expect_rejection(
            lambda: service.get_report(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # GET /research/runs/{run_id}/evidence
        await expect_rejection(
            lambda: service.list_evidence(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )
        # GET /research/runs/{run_id}/findings
        await expect_rejection(
            lambda: service.list_findings(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected=expected,
        )


# ---------------------------------------------------------------------------
# 4. 内容草稿 / 发布记录：读取 / 编辑 / 审核 / 确认发布
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id, expected", ACTORS, ids=ACTOR_IDS)
async def test_04_content_draft_and_publish_reject_foreign_access(matrix, actor_id, expected):
    factory, ids = matrix
    tenant_id, user_id = _actor_ids(ids, actor_id)
    draft_id, publish_id = ids["draft"], ids["publish"]
    async with factory() as session:
        service = ContentService(session)

        # 按 ID 的草稿/发布记录操作：跨租户 B → 404 语义；非成员 C → 403 语义。
        # PATCH /content/drafts/{draft_id}
        await expect_rejection(
            lambda: service.update_draft(draft_id=draft_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False, data={"title": "hacked"}),
            expected=expected,
        )
        # POST /content/drafts/{draft_id}/review
        await expect_rejection(
            lambda: service.review_draft(draft_id=draft_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False, status="approved"),
            expected=expected,
        )
        # POST /content/publishes/{publish_id}/confirm
        await expect_rejection(
            lambda: service.confirm_publish(publish_id=publish_id, tenant_id=tenant_id, user_id=user_id, is_superuser=False, data={}),
            expected=expected,
        )
        # 工作空间维度的列表端点无法逐条 404，未授权一律 PermissionError（403）。
        # GET /content/drafts?workspace_id=...
        await expect_rejection(
            lambda: service.list_drafts(workspace_id=ids["ws_a"], tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected="forbidden",
        )
        # GET /content/publishes?workspace_id=...
        await expect_rejection(
            lambda: service.list_publishes(workspace_id=ids["ws_a"], tenant_id=tenant_id, user_id=user_id, is_superuser=False),
            expected="forbidden",
        )


# ---------------------------------------------------------------------------
# 5. 工作台聚合：/workbench/search 与 /workbench/tasks 的租户/工作空间隔离
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id", ACTOR_IDS)
async def test_05_workbench_search_and_tasks_isolated(matrix, actor_id):
    """隔离断言：未授权者直接访问 WA 得到 403；在自己可见空间内检索不到租户 A 条目。"""
    factory, ids = matrix
    own_tenant, own_user = _actor_ids(ids, actor_id)
    own_ws, decoy = (ids["ws_c"], ids["decoy_c"]) if actor_id == "non_member_c" else (ids["ws_b"], ids["decoy_b"])

    async with factory() as session:
        service = WorkbenchService(session)

        # 直接以租户 A 的工作空间为参数调用聚合接口：必须 PermissionError（403）。
        await expect_rejection(
            lambda: service.search(query="secret", workspace_id=ids["ws_a"], tenant_id=own_tenant, user_id=own_user),
            expected="forbidden",
        )
        await expect_rejection(
            lambda: service.list_tasks(workspace_id=ids["ws_a"], tenant_id=own_tenant, user_id=own_user),
            expected="forbidden",
        )

        # 在自己可见的工作空间内搜索租户 A 的标记词：结果必须为空（无跨租户泄漏）。
        result = await service.search(query="secret", workspace_id=own_ws, tenant_id=own_tenant, user_id=own_user)
        assert result["total"] == 0, f"搜索结果泄漏租户 A 条目: {result['items']}"
        assert result["items"] == []

        # 诱饵检索：证明查询真实执行，且只命中自己工作空间的条目。
        result = await service.search(query="decoy-task", workspace_id=own_ws, tenant_id=own_tenant, user_id=own_user)
        assert result["total"] == 1, f"诱饵检索应恰好命中 1 条，实际 {result['total']}"
        assert str(result["items"][0]["id"]) == str(decoy)

        # 任务聚合：只含自己工作空间的待办，且不含租户 A 的任何资源 ID。
        result = await service.list_tasks(workspace_id=own_ws, tenant_id=own_tenant, user_id=own_user)
        assert result["total"] == 1, f"任务聚合应只含自己工作空间的 1 条待办，实际 {result['total']}"
        assert str(result["items"][0]["id"]) == str(decoy)
        tenant_a_resource_ids = {str(ids[key]) for key in ("asset", "knowledge", "run", "draft", "publish", "dataset", "project")}
        returned_ids = {str(task["id"]) for task in result["items"]}
        assert tenant_a_resource_ids.isdisjoint(returned_ids), f"任务聚合泄漏租户 A 资源: {returned_ids & tenant_a_resource_ids}"


# ---------------------------------------------------------------------------
# 6. 基座文档 / 数据集：读取 / 删除（守卫位于路由层，沿真实调用路径验证）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id", ACTOR_IDS)
async def test_06_dataset_and_document_endpoints_reject_foreign_access(matrix, actor_id):
    """datasets.py / documents.py 的每个端点都先执行 verify_dataset_access。

    DatasetServiceImpl.get_dataset / delete_dataset、DocumentServiceImpl.get_document /
    delete_document 本身不做租户校验（裸查 ID），租户边界完全依赖路由层守卫；
    因此本用例按 API 真实调用顺序：守卫调用（PermissionError → 403）。
    """
    factory, ids = matrix
    tenant_id, user_id = _actor_ids(ids, actor_id)
    async with factory() as session:
        dataset_service = DatasetServiceImpl(session)
        document_service = DocumentServiceImpl(session)

        # GET /datasets/{dataset_id} 与 DELETE /datasets/{dataset_id} 的路由守卫
        # （datasets.py：读取 action="read"，删除 action="write"）。
        await expect_rejection(
            lambda: dataset_service.verify_dataset_access(dataset_id=ids["dataset"], user_id=user_id, tenant_id=tenant_id, action="read"),
            expected="forbidden",
        )
        await expect_rejection(
            lambda: dataset_service.verify_dataset_access(dataset_id=ids["dataset"], user_id=user_id, tenant_id=tenant_id, action="write"),
            expected="forbidden",
        )

        # GET /documents/{document_id} 的真实路由序列（documents.py _verify_document_access）：
        # 先由服务层加载文档（服务层裸查 ID），再用文档所属数据集执行守卫。
        document = await document_service.get_document(ids["document"])
        assert document is not None and document["dataset_id"] == str(ids["dataset"])
        await expect_rejection(
            lambda: dataset_service.verify_dataset_access(dataset_id=ids["dataset"], user_id=user_id, tenant_id=tenant_id, action="read"),
            expected="forbidden",
        )

        # DELETE /documents/{document_id} 的守卫（documents.py：action="write"）。
        await expect_rejection(
            lambda: dataset_service.verify_dataset_access(dataset_id=ids["dataset"], user_id=user_id, tenant_id=tenant_id, action="write"),
            expected="forbidden",
        )


# ---------------------------------------------------------------------------
# 7. 知识回流（C-10~C-12 新增写路径）：回流只能经守卫后的 review/rollback 触达
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id, expected", ACTORS, ids=ACTOR_IDS)
async def test_07_knowledge_backflow_write_path_is_guarded(matrix, actor_id, expected, monkeypatch):
    """未授权用户即使触发 review/rollback 也被拒绝，且不会产生回流文档。

    KNOWN 弱断言背景：基座 Document 本身无服务层租户过滤（登记债务），
    本用例验证的是新增回流写路径的可达性守卫：守卫拒绝 → 回流不存在。
    """
    from sqlalchemy import select

    from infrastructure.database.models import Document
    from services.impl.knowledge_backflow_service import card_file_name

    monkeypatch.setenv("KNOWLEDGE_BACKFLOW_ENABLED", "1")
    factory, ids = matrix
    tenant_id, user_id = _actor_ids(ids, actor_id)
    owner_tenant, owner_user = ids["tenant_a"], ids["owner_a"]

    async with factory() as session:
        service = KnowledgeService(session)
        created = await service.create_item(
            tenant_id=owner_tenant, user_id=owner_user, is_superuser=False,
            workspace_id=ids["ws_a"], title="backflow-guard-card", item_type="concept",
            definition="回流守卫用例", metadata={"source": "manual"},
        )
        await service.add_evidence(
            item_id=created["id"], tenant_id=owner_tenant, user_id=owner_user, is_superuser=False,
            document_id=str(ids["document"]), quote="守卫用例证据",
        )

        await expect_rejection(
            lambda: service.review_item(
                item_id=created["id"], tenant_id=tenant_id, user_id=user_id,
                is_superuser=False, review_status="approved",
            ),
            expected=expected,
        )
        leaked = (
            await session.execute(select(Document).where(Document.file_name == card_file_name(created["id"])))
        ).scalar_one_or_none()
        assert leaked is None, "被拒绝的 review 不允许产生任何回流文档"

        approved = await service.review_item(
            item_id=created["id"], tenant_id=owner_tenant, user_id=owner_user,
            is_superuser=False, review_status="approved",
        )
        assert approved["review_status"] == "approved"
        backflow_doc = (
            await session.execute(select(Document).where(Document.file_name == card_file_name(created["id"])))
        ).scalar_one_or_none()
        assert backflow_doc is not None, "属主 approve 后回流文档必须存在"
