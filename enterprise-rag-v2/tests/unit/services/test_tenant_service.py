"""
单元测试 - 租户服务
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.impl.tenant_service import TenantServiceImpl
from infrastructure.database.models import Tenant, Workspace, Dataset


class TestTenantServiceImpl:
    """TenantServiceImpl单元测试"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one.return_value = 0
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def tenant_service(self, mock_session):
        """创建TenantServiceImpl实例"""
        return TenantServiceImpl(session=mock_session)

    @pytest.fixture
    def sample_tenant_data(self):
        """示例租户数据"""
        return {
            "name": "Test Tenant",
            "contact_email": "test@example.com",
            "contact_phone": "1234567890",
            "plan": "free",
            "metadata": {"key": "value"}
        }

    @pytest.mark.asyncio
    async def test_create_tenant_success(self, tenant_service, sample_tenant_data):
        """测试成功创建租户"""
        with patch.object(tenant_service.tenant_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email, \
             patch.object(tenant_service.tenant_repo, 'create', new_callable=AsyncMock) as mock_create, \
             patch('services.impl.tenant_service.WorkspaceServiceImpl') as mock_ws_cls, \
             patch('services.impl.tenant_service.DatasetServiceImpl') as mock_ds_cls, \
             patch('services.impl.tenant_service.DocumentCopyServiceImpl') as mock_copy_cls:

            mock_get_email.return_value = None

            tenant_id = uuid4()
            mock_tenant = MagicMock()
            mock_tenant.id = tenant_id
            mock_tenant.name = sample_tenant_data["name"]
            mock_tenant.contact_email = sample_tenant_data["contact_email"]
            mock_tenant.contact_phone = sample_tenant_data["contact_phone"]
            mock_tenant.plan = MagicMock(value="free")
            mock_tenant.status = MagicMock(value="active")
            mock_tenant.metadata = sample_tenant_data["metadata"]
            mock_tenant.created_at = datetime.utcnow()

            mock_create.return_value = mock_tenant

            # 模拟工作空间服务
            mock_ws_instance = MagicMock()
            mock_ws_instance.create_workspace = AsyncMock(return_value={
                "id": str(uuid4()),
                "name": "默认工作空间"
            })
            mock_ws_cls.return_value = mock_ws_instance

            # 模拟数据集服务
            mock_ds_instance = MagicMock()
            mock_ds_instance.create_dataset = AsyncMock(return_value={
                "id": str(uuid4()),
                "name": "公共知识库"
            })
            mock_ds_cls.return_value = mock_ds_instance

            # 模拟文档复制服务
            mock_copy_instance = MagicMock()
            mock_copy_instance.get_system_template_workspace = AsyncMock(return_value=MagicMock())
            mock_copy_instance.copy_template_documents = AsyncMock(return_value=[])
            mock_copy_cls.return_value = mock_copy_instance

            result = await tenant_service.create_tenant(
                name=sample_tenant_data["name"],
                contact_email=sample_tenant_data["contact_email"],
                contact_phone=sample_tenant_data["contact_phone"],
                plan=sample_tenant_data["plan"],
                metadata=sample_tenant_data["metadata"]
            )

            assert result["name"] == sample_tenant_data["name"]
            assert result["contact_email"] == sample_tenant_data["contact_email"]
            assert "id" in result

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_email(self, tenant_service, sample_tenant_data):
        """测试重复邮箱创建租户失败"""
        with patch.object(tenant_service.tenant_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email:
            mock_get_email.return_value = Tenant(
                id=uuid4(),
                name="Existing",
                contact_email=sample_tenant_data["contact_email"],
                plan="free"
            )

            with pytest.raises(ValueError, match="该邮箱已被使用"):
                await tenant_service.create_tenant(
                    name=sample_tenant_data["name"],
                    contact_email=sample_tenant_data["contact_email"]
                )

    @pytest.mark.asyncio
    async def test_get_tenant_success(self, tenant_service):
        """测试成功获取租户"""
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.contact_email = "test@example.com"
        mock_tenant.contact_phone = "1234567890"
        mock_tenant.plan = MagicMock(value="pro")
        mock_tenant.status = MagicMock(value="active")
        mock_tenant.metadata = {}
        mock_tenant.created_at = datetime.utcnow()
        mock_tenant.updated_at = datetime.utcnow()

        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = mock_tenant

            result = await tenant_service.get_tenant(tenant_id)

            assert result is not None
            assert result["name"] == "Test Tenant"
            assert result["id"] == str(tenant_id)

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self, tenant_service):
        """测试获取不存在的租户"""
        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            result = await tenant_service.get_tenant(uuid4())

            assert result is None

    @pytest.mark.asyncio
    async def test_update_tenant_success(self, tenant_service):
        """测试成功更新租户"""
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Old Name"
        mock_tenant.contact_email = "old@example.com"
        mock_tenant.contact_phone = None
        mock_tenant.plan = "free"
        mock_tenant.status = MagicMock(value="active")
        mock_tenant.metadata = {}
        mock_tenant.created_at = datetime.utcnow()
        mock_tenant.updated_at = datetime.utcnow()

        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id, \
             patch.object(tenant_service.tenant_repo, 'update', new_callable=AsyncMock) as mock_update:

            mock_get_by_id.return_value = mock_tenant
            mock_update.return_value = mock_tenant

            result = await tenant_service.update_tenant(
                tenant_id=tenant_id,
                name="New Name"
            )

            assert result is not None
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_tenant_not_found(self, tenant_service):
        """测试更新不存在的租户"""
        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            with pytest.raises(ValueError, match="租户不存在"):
                await tenant_service.update_tenant(
                    tenant_id=uuid4(),
                    name="New Name"
                )

    @pytest.mark.asyncio
    async def test_delete_tenant_success(self, tenant_service, mock_session):
        """测试成功删除租户（真删除）"""
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.status = "active"

        mock_workspace_result = MagicMock()
        mock_workspace_result.scalars.return_value.all.return_value = []
        mock_dataset_result = MagicMock()
        mock_dataset_result.scalars.return_value.all.return_value = []
        mock_user_result = MagicMock()
        mock_user_result.scalars.return_value.all.return_value = []

        async def mock_execute_side_effect(query):
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            stmt_str = str(query)
            if 'Workspace' in stmt_str and 'tenant_id' in stmt_str:
                result = mock_workspace_result
            elif 'Dataset' in stmt_str:
                result = mock_dataset_result
            elif 'User' in stmt_str:
                result = mock_user_result
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id, \
             patch.object(tenant_service.audit_service, 'log', new_callable=AsyncMock) as mock_audit_log:
            mock_get_by_id.return_value = mock_tenant

            result = await tenant_service.delete_tenant(tenant_id)

            assert result is True
            # 租户删除已改为数据库级批量级联（sqlalchemy delete 语句 + flush），不再使用 ORM session.delete。
            assert mock_session.execute.await_count >= 1
            mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_tenant_not_found(self, tenant_service):
        """测试删除不存在的租户"""
        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            result = await tenant_service.delete_tenant(uuid4())

            assert result is False

    @pytest.mark.asyncio
    async def test_list_tenants_with_pagination(self, tenant_service):
        """测试分页查询租户列表"""
        from core.value_objects.pagination import Page, Pagination

        mock_tenant = MagicMock()
        mock_tenant.id = uuid4()
        mock_tenant.name = "Test Tenant"
        mock_tenant.contact_email = "test@example.com"
        mock_tenant.contact_phone = None
        mock_tenant.plan = MagicMock(value="free")
        mock_tenant.status = MagicMock(value="active")
        mock_tenant.metadata = {}
        mock_tenant.created_at = datetime.utcnow()

        mock_page = Page(
            items=[mock_tenant],
            total=1,
            page=1,
            page_size=20
        )

        with patch.object(tenant_service.tenant_repo, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_page

            pagination = Pagination(page=1, page_size=20)
            result = await tenant_service.list_tenants(pagination=pagination)

            assert result.total == 1
            assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_list_tenants_with_filters(self, tenant_service):
        """测试带过滤条件查询租户列表"""
        from core.value_objects.pagination import Page, Pagination

        mock_page = Page(
            items=[],
            total=0,
            page=1,
            page_size=20
        )

        with patch.object(tenant_service.tenant_repo, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_page

            pagination = Pagination(page=1, page_size=20)
            result = await tenant_service.list_tenants(
                status="active",
                plan="pro",
                pagination=pagination
            )

            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tenant_usage(self, tenant_service):
        """测试获取租户使用情况"""
        tenant_id = uuid4()

        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id

        usage = {
            "user_count": 1,
            "workspace_count": 1,
            "dataset_count": 1,
            "document_count": 5,
            "storage_mb": 1.0,
        }
        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)), \
             patch.object(tenant_service, "_get_current_usage", AsyncMock(return_value=usage)), \
             patch.object(tenant_service, "get_quota_status", AsyncMock(return_value={"plan": "free"})):

            result = await tenant_service.get_tenant_usage(tenant_id)

            assert "tenant_id" in result
            assert result["usage"]["user_count"] == 1
            assert "quota_status" in result

    @pytest.mark.asyncio
    async def test_get_tenant_usage_tenant_not_found(self, tenant_service):
        """测试获取不存在租户的使用情况"""
        with patch.object(tenant_service.tenant_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            with pytest.raises(ValueError, match="租户不存在"):
                await tenant_service.get_tenant_usage(uuid4())

    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self, tenant_service, mock_session):
        """测试检查配额在限制内（依赖 session.execute 返回用量）"""
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.plan.value = "free"

        def _scalar_results(user_c, ws_c, ds_c, doc_c, storage=0):
            out = []
            for v in (user_c, ws_c, ds_c, doc_c):
                r = MagicMock()
                r.scalar.return_value = v
                out.append(r)
            r5 = MagicMock()
            r5.scalar.return_value = storage
            out.append(r5)
            return out

        mock_session.execute = AsyncMock(side_effect=_scalar_results(1, 1, 1, 1, 0))
        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            assert await tenant_service.check_quota(tenant_id, "document") is True

    @pytest.mark.asyncio
    async def test_legacy_free_plan_does_not_limit_documents(self, tenant_service, mock_session):
        """历史 free 计划字段不再限制开源版资源。"""
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.plan.value = "free"

        def _scalar_results(user_c, ws_c, ds_c, doc_c, storage=0):
            out = []
            for v in (user_c, ws_c, ds_c, doc_c):
                r = MagicMock()
                r.scalar.return_value = v
                out.append(r)
            r5 = MagicMock()
            r5.scalar.return_value = storage
            out.append(r5)
            return out

        mock_session.execute = AsyncMock(side_effect=_scalar_results(1, 1, 1, 200, 0))
        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            assert await tenant_service.check_quota(tenant_id, "document") is True

    @pytest.mark.asyncio
    async def test_create_tenant_with_default_workspace(self, tenant_service, sample_tenant_data):
        """测试创建租户时自动创建默认工作空间和公共知识库"""
        with patch.object(tenant_service.tenant_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email, \
             patch.object(tenant_service.tenant_repo, 'create', new_callable=AsyncMock) as mock_create, \
             patch('services.impl.tenant_service.WorkspaceServiceImpl') as mock_workspace_service, \
             patch('services.impl.tenant_service.DatasetServiceImpl') as mock_dataset_service, \
             patch('services.impl.tenant_service.DocumentCopyServiceImpl') as mock_copy_service, \
             patch('services.impl.tenant_service.UserServiceImpl') as mock_user_service, \
             patch('infrastructure.queue.document_tasks.copy_template_documents_task.delay') as mock_copy_delay:

            mock_get_email.return_value = None

            tenant_id = uuid4()
            mock_tenant = MagicMock()
            mock_tenant.id = tenant_id
            mock_tenant.name = sample_tenant_data["name"]
            mock_tenant.contact_email = sample_tenant_data["contact_email"]
            mock_tenant.plan = MagicMock(value="free")
            mock_tenant.status = MagicMock(value="active")
            mock_tenant.metadata = sample_tenant_data["metadata"]
            mock_tenant.created_at = datetime.utcnow()

            mock_create.return_value = mock_tenant

            # 模拟用户服务
            mock_user_instance = MagicMock()
            mock_admin_user = MagicMock()
            mock_admin_user.id = str(uuid4())
            mock_admin_user.username = "admin"
            mock_user_instance.create_user = AsyncMock(return_value=mock_admin_user)
            mock_user_service.return_value = mock_user_instance

            # 模拟工作空间服务
            mock_ws_instance = MagicMock()
            mock_ws_instance.create_workspace = AsyncMock(return_value={
                "id": str(uuid4()),
                "name": "默认工作空间"
            })
            mock_workspace_service.return_value = mock_ws_instance

            # 模拟数据集服务
            mock_dataset_instance = MagicMock()
            mock_dataset_instance.create_dataset = AsyncMock(return_value={
                "id": str(uuid4()),
                "name": "公共知识库"
            })
            mock_dataset_service.return_value = mock_dataset_instance

            # 模拟文档复制服务（get_system_template_workspace 直接调用）
            mock_copy_instance = MagicMock()
            mock_copy_instance.get_system_template_workspace = AsyncMock(return_value=MagicMock())
            mock_copy_service.return_value = mock_copy_instance

            # 模拟 Celery 异步复制任务
            mock_copy_delay.return_value = MagicMock(id="fake_task_id")

            result = await tenant_service.create_tenant(
                name=sample_tenant_data["name"],
                contact_email=sample_tenant_data["contact_email"],
                admin_username="admin",
                admin_email="admin@example.com",
                admin_password="Admin123!@#"
            )

            assert result["name"] == sample_tenant_data["name"]
            # 验证用户服务被调用
            mock_user_instance.create_user.assert_called_once()
            # 验证工作空间服务被调用
            mock_ws_instance.create_workspace.assert_called_once()
            # 验证数据集服务被调用
            mock_dataset_instance.create_dataset.assert_called_once()
            # 验证文档复制任务投入队列（Celery task.delay）
            mock_copy_delay.assert_called_once()
