from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.internal_admin.routers.quotas import get_quota_overrides, update_quota


@pytest.mark.asyncio
async def test_update_quota_success():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                db=mock_db,
                quota_service=SimpleNamespace(redis=mock_redis),
            )
        )
    )
    identity = {
        "operation_id": "ops_quota_1",
        "operator": "tester",
        "request_id": "req_1",
        "client_ip": "127.0.0.1",
    }
    body = {"quota_type": "documents", "value": 123, "reason": "ops adjust", "operator_id": "ops_user_1"}

    with patch("api.internal_admin.routers.quotas.OperationService") as op_cls, patch(
        "api.internal_admin.routers.quotas.QuotaOverrideService"
    ) as qos_cls:
        op_svc = op_cls.return_value
        op_svc.create_pending_operation = AsyncMock()
        op_svc.mark_succeeded = AsyncMock()
        op_svc.mark_failed = AsyncMock()

        qos = qos_cls.return_value
        qos.set_override = AsyncMock(
            return_value={"tenant_id": "tenant_1", "dimension": "documents", "override_value": 123}
        )

        result = await update_quota(
            tenant_id="tenant_1",
            body=body,
            request=request,
            identity=identity,
        )

    assert result["success"] is True
    assert result["data"]["override_value"] == 123
    qos.set_override.assert_awaited_once()
    assert qos.set_override.await_args.kwargs["created_by"] == "ops_user_1"


@pytest.mark.asyncio
async def test_get_quota_overrides_success():
    mock_db = MagicMock()
    mock_db.fetch_all = AsyncMock(
        return_value=[{"tenant_id": "tenant_1", "dimension": "documents", "override_value": 100}]
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=mock_db)))
    identity = {"request_id": "req_1"}

    result = await get_quota_overrides("tenant_1", request, identity)

    assert result["success"] is True
    assert result["meta"]["tenant_id"] == "tenant_1"
    assert len(result["data"]) == 1
