from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.internal_admin.routers.audit import list_audit_logs


@pytest.mark.asyncio
async def test_list_audit_logs_success():
    mock_db = MagicMock()
    mock_db.fetch_all = AsyncMock(
        return_value=[
            {"id": "a1", "action": "TENANT_UPDATE", "status": "success"},
        ]
    )
    mock_db.fetch_one = AsyncMock(return_value={"total": 1})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=mock_db)))
    identity = {"request_id": "req_1"}

    result = await list_audit_logs(
        request=request,
        identity=identity,
        tenant_id=None,
        action=None,
        resource_type=None,
        status=None,
        start_at=None,
        end_at=None,
        page=1,
        page_size=20,
    )

    assert result["success"] is True
    assert result["meta"]["total"] == 1
    assert result["meta"]["total_pages"] == 1
    assert result["data"][0]["id"] == "a1"
