"""
配额管理测试
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from services.impl.tenant_service import (
    TenantServiceImpl,
    QuotaExceededError,
    DEFAULT_QUOTAS,
)


@pytest.fixture
def mock_session():
    session = MagicMock()
    res = MagicMock()
    res.all.return_value = []
    res.scalars.return_value.all.return_value = []
    res.scalar_one_or_none.return_value = None
    res.scalar.return_value = 0
    session.execute = AsyncMock(return_value=res)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


@pytest.fixture
def tenant_service(mock_session):
    return TenantServiceImpl(mock_session)


def _usage_execute_results(user_count: int, workspace=0, dataset=0, document=0, storage_sum=0):
    """_get_current_usage 连续 5 次 execute，前四次 scalar 为计数，最后一次为 storage sum。"""
    out = []
    for v in (user_count, workspace, dataset, document):
        r = MagicMock()
        r.scalar.return_value = v
        out.append(r)
    r5 = MagicMock()
    r5.scalar.return_value = storage_sum
    out.append(r5)
    return out


class TestQuotaManagement:
    """配额管理测试"""

    def test_default_quotas_defined(self):
        assert all(limit == -1 for limit in DEFAULT_QUOTAS.values())

    @pytest.mark.asyncio
    async def test_check_quota_returns_true_for_unlimited(self, tenant_service, mock_session):
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.plan.value = "enterprise"

        mock_session.execute = AsyncMock(side_effect=_usage_execute_results(100, 10, 10, 10, 0))

        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            result = await tenant_service.check_quota(tenant_id, "user")
            assert result is True

    @pytest.mark.asyncio
    async def test_legacy_plan_does_not_limit_resources(self, tenant_service, mock_session):
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.plan.value = "free"

        mock_session.execute = AsyncMock(side_effect=_usage_execute_results(10, 0, 0, 0, 0))

        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            result = await tenant_service.check_quota(tenant_id, "user")
            assert result is True

    @pytest.mark.asyncio
    async def test_legacy_free_plan_does_not_raise_at_usage_threshold(self, tenant_service, mock_session):
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.plan.value = "free"

        mock_session.execute = AsyncMock(side_effect=_usage_execute_results(10, 0, 0, 0, 0))

        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            await tenant_service.check_quota_and_raise(tenant_id, "user")

    @pytest.mark.asyncio
    async def test_get_quota_status(self, tenant_service, mock_session):
        tenant_id = uuid4()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.plan.value = "free"

        mock_session.execute = AsyncMock(
            side_effect=_usage_execute_results(3, 1, 2, 5, 10000000)
        )

        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            status = await tenant_service.get_quota_status(tenant_id)

            assert "tenant_id" in status
            assert "plan" in status
            assert "quotas" in status
            assert "usage" in status
            assert "status" in status
            assert "warnings" in status


class TestQuotaExceededError:
    """配额超限异常测试"""

    def test_exception_message(self):
        error = QuotaExceededError("user", 10, 5)

        assert error.resource_type == "user"
        assert error.current == 10
        assert error.limit == 5
        assert "user" in str(error)
        assert "10" in str(error)
        assert "5" in str(error)


class TestTenantServiceAudit:
    """租户服务审计测试"""

    @pytest.mark.asyncio
    async def test_create_tenant_logs_audit(self, tenant_service, mock_session):
        tenant_id = uuid4()

        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.contact_email = "test@example.com"
        mock_tenant.plan.value = "free"
        mock_tenant.status.value = "active"
        mock_tenant.extra_metadata = {}
        mock_tenant.created_at = datetime.utcnow()

        with patch.object(tenant_service.tenant_repo, "get_by_email", AsyncMock(return_value=None)):
            with patch.object(tenant_service.tenant_repo, "create", AsyncMock(return_value=mock_tenant)):
                with patch.object(tenant_service.audit_service, "log", AsyncMock(return_value=None)):
                    with patch('services.impl.tenant_service.WorkspaceServiceImpl') as mock_ws_cls, \
                         patch('services.impl.tenant_service.DatasetServiceImpl') as mock_ds_cls, \
                         patch('services.impl.tenant_service.DocumentCopyServiceImpl') as mock_copy_cls:
                        mock_ws_instance = MagicMock()
                        mock_ws_instance.create_workspace = AsyncMock(return_value={"id": str(uuid4()), "name": "默认工作空间"})
                        mock_ws_cls.return_value = mock_ws_instance
                        mock_ds_instance = MagicMock()
                        mock_ds_instance.create_dataset = AsyncMock(return_value={"id": str(uuid4()), "name": "公共知识库"})
                        mock_ds_cls.return_value = mock_ds_instance
                        mock_copy_instance = MagicMock()
                        mock_copy_instance.get_system_template_workspace = AsyncMock(return_value=MagicMock())
                        mock_copy_instance.copy_template_documents = AsyncMock(return_value=[])
                        mock_copy_cls.return_value = mock_copy_instance

                        await tenant_service.create_tenant(
                            name="Test Tenant",
                            contact_email="test@example.com",
                            plan="free",
                        )

                        tenant_service.audit_service.log.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_tenant_logs_audit(self, tenant_service, mock_session):
        tenant_id = uuid4()

        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"

        with patch.object(tenant_service.tenant_repo, "get_by_id", AsyncMock(return_value=mock_tenant)):
            with patch.object(tenant_service.tenant_repo, "update", AsyncMock(return_value=mock_tenant)):
                with patch.object(tenant_service.audit_service, "log", AsyncMock(return_value=None)):
                    result = await tenant_service.delete_tenant(tenant_id)

                    assert result is True
                    tenant_service.audit_service.log.assert_awaited()
