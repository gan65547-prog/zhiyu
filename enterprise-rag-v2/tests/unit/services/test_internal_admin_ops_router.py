import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from api.internal_admin.routers.ops import (
    list_operations,
    get_operation_detail,
    get_operation_tasks,
)


@pytest.mark.asyncio
async def test_list_operations_success():
    mock_db = MagicMock()
    mock_db.fetch_all = AsyncMock(return_value=[{"operation_id": "op_1", "status": "SUCCEEDED"}])
    mock_db.fetch_one = AsyncMock(return_value={"total": 1})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=mock_db)))
    identity = {"request_id": "req_1"}

    result = await list_operations(request, identity, None, None, None, 1, 20)
    assert result["success"] is True
    assert result["meta"]["total"] == 1
    assert result["meta"]["total_pages"] == 1
    assert result["meta"]["has_next"] is False
    assert result["meta"]["has_prev"] is False


@pytest.mark.asyncio
async def test_get_operation_detail_not_found():
    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value=None)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=mock_db)))
    identity = {"request_id": "req_1"}

    with pytest.raises(HTTPException) as exc:
        await get_operation_detail("op_not_found", request, identity)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_operation_tasks_success():
    mock_db = MagicMock()
    mock_db.fetch_all = AsyncMock(return_value=[{"task_id": "task_1", "event_type": "DISPATCHED"}])
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=mock_db)))
    identity = {"request_id": "req_1"}

    result = await get_operation_tasks("op_1", request, identity)
    assert result["success"] is True
    assert len(result["data"]) == 1

