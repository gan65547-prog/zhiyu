from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.internal_admin.routers.documents import dispatch_reindex


@pytest.mark.asyncio
async def test_dispatch_reindex_success():
    mock_db = MagicMock()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=mock_db)))
    identity = {
        "operation_id": "ops_reindex_1",
        "operator": "tester",
        "request_id": "req_1",
        "client_ip": "127.0.0.1",
    }
    body = {"tenant_id": "tenant_1", "dataset_id": "ds_1"}

    with patch("api.internal_admin.routers.documents.OperationService") as op_cls, patch(
        "api.internal_admin.routers.documents.ops_reindex_documents"
    ) as task_mod:
        op_svc = op_cls.return_value
        op_svc.create_pending_operation = AsyncMock()
        op_svc.mark_running = AsyncMock()
        op_svc.create_task_event = AsyncMock()
        op_svc.mark_failed = AsyncMock()
        task_mod.apply_async.return_value = SimpleNamespace(id="task_1")

        result = await dispatch_reindex(body=body, request=request, identity=identity)

    assert result["success"] is True
    assert result["data"]["task_id"] == "task_1"
