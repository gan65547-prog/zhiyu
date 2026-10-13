from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.routers.chat import chat_async_submit, chat_async_job_status
from api.schemas.chat import ChatRequest


class _FakeRedis:
    """避免单测调用 get_redis() 去连真实 localhost:6379。"""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self._store[key] = value

    async def get(self, key: str):
        return self._store.get(key)


class _DummyAsyncResult:
    def __init__(self, state: str, result):
        self.state = state
        self.result = result


@pytest.mark.asyncio
async def test_chat_async_submit_success(monkeypatch):
    dataset_id = str(uuid4())
    fake_redis = _FakeRedis()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=fake_redis)))
    chat_service = MagicMock()
    chat_service.verify_dataset_access = AsyncMock()
    quota_service = MagicMock()
    quota_service.check_and_increment = AsyncMock()
    current_user = {"sub": str(uuid4()), "tenant_id": str(uuid4())}

    dummy_task = SimpleNamespace(id="job-123")
    apply_async_mock = MagicMock(return_value=dummy_task)
    monkeypatch.setattr(
        "api.routers.chat.process_chat_async_task",
        SimpleNamespace(apply_async=apply_async_mock),
    )

    body = ChatRequest(dataset_id=dataset_id, query="hello async")
    result = await chat_async_submit(
        request=request,
        body=body,
        chat_service=chat_service,
        current_user=current_user,
        quota_service=quota_service,
    )

    assert result["success"] is True
    assert result["data"]["job_id"] == "job-123"
    assert result["data"]["status"] == "PENDING"
    assert apply_async_mock.called
    assert apply_async_mock.call_args.kwargs["queue"] == "chat_async"
    chat_service.verify_dataset_access.assert_awaited_once()
    quota_service.check_and_increment.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_async_job_status_success(monkeypatch):
    user_id = str(uuid4())
    job_id = "job-456"
    fake_redis = _FakeRedis()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=fake_redis)))

    # 先提交一次 owner 绑定（通过 submit 接口缓存归属）
    monkeypatch.setattr(
        "api.routers.chat.process_chat_async_task",
        SimpleNamespace(apply_async=MagicMock(return_value=SimpleNamespace(id=job_id))),
    )
    body = ChatRequest(dataset_id=str(uuid4()), query="test")
    chat_service = MagicMock()
    chat_service.verify_dataset_access = AsyncMock()
    quota_service = MagicMock()
    quota_service.check_and_increment = AsyncMock()
    await chat_async_submit(
        request=request,
        body=body,
        chat_service=chat_service,
        current_user={"sub": user_id, "tenant_id": str(uuid4())},
        quota_service=quota_service,
    )

    monkeypatch.setattr(
        "api.routers.chat.AsyncResult",
        lambda jid, app=None: _DummyAsyncResult("SUCCESS", {"conversation_id": str(uuid4())}),
    )
    result = await chat_async_job_status(
        request=request,
        job_id=job_id,
        current_user={"sub": user_id},
    )

    assert result["success"] is True
    assert result["data"]["job_id"] == job_id
    assert result["data"]["status"] == "SUCCESS"
    assert "conversation_id" in result["data"]["result"]


@pytest.mark.asyncio
async def test_chat_async_job_status_forbidden_for_other_user(monkeypatch):
    fake_redis = _FakeRedis()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=fake_redis)))
    owner_id = str(uuid4())
    other_id = str(uuid4())
    job_id = "job-789"

    monkeypatch.setattr(
        "api.routers.chat.process_chat_async_task",
        SimpleNamespace(apply_async=MagicMock(return_value=SimpleNamespace(id=job_id))),
    )

    body = ChatRequest(dataset_id=str(uuid4()), query="isolation")
    chat_service = MagicMock()
    chat_service.verify_dataset_access = AsyncMock()
    quota_service = MagicMock()
    quota_service.check_and_increment = AsyncMock()
    await chat_async_submit(
        request=request,
        body=body,
        chat_service=chat_service,
        current_user={"sub": owner_id, "tenant_id": str(uuid4())},
        quota_service=quota_service,
    )

    monkeypatch.setattr(
        "api.routers.chat.AsyncResult",
        lambda jid, app=None: _DummyAsyncResult("PENDING", None),
    )

    with pytest.raises(HTTPException) as exc:
        await chat_async_job_status(
            request=request,
            job_id=job_id,
            current_user={"sub": other_id},
        )

    assert exc.value.status_code == 404

