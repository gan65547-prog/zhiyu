import httpx
import pytest

from core.rag.vector_store import VectorStore


class _Response:
    status_code = 200
    text = ""


class _Client:
    def __init__(self, error=None):
        self.error = error
        self.closed = False

    async def put(self, *args, **kwargs):
        if self.error:
            raise self.error
        return _Response()

    async def aclose(self):
        self.closed = True


class _StatusClient(_Client):
    def __init__(self, status_code):
        super().__init__()
        self.status_code = status_code

    async def put(self, *args, **kwargs):
        response = _Response()
        response.status_code = self.status_code
        return response


@pytest.mark.asyncio
async def test_create_collection_waits_for_qdrant_create_race(monkeypatch):
    store = VectorStore(collection_name="race_collection")
    client = _StatusClient(409)
    states = iter([False, False, True])

    async def get_client():
        return client

    async def collection_exists():
        return next(states)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(store, "_get_client", get_client)
    monkeypatch.setattr(store, "collection_exists", collection_exists)
    monkeypatch.setattr("core.rag.vector_store.asyncio.sleep", no_sleep)

    assert await store.create_collection(vector_size=2) is True


@pytest.mark.asyncio
async def test_upsert_recreates_client_after_transient_disconnect(monkeypatch):
    store = VectorStore(collection_name="test_collection")
    failed = _Client(httpx.RemoteProtocolError("server disconnected"))
    healthy = _Client()
    clients = iter([failed, healthy])

    async def get_client():
        return next(clients)

    async def collection_exists():
        return True

    monkeypatch.setattr(store, "_get_client", get_client)
    monkeypatch.setattr(store, "collection_exists", collection_exists)
    store._client = failed

    assert await store.upsert([{"id": "point-1", "vector": [0.1], "payload": {}}]) is True
    assert failed.closed is True


@pytest.mark.asyncio
async def test_upsert_precreates_missing_collection(monkeypatch):
    store = VectorStore(collection_name="missing_collection")
    healthy = _Client()
    created_sizes = []

    async def get_client():
        return healthy

    async def collection_exists():
        return False

    async def create_collection(vector_size=None):
        created_sizes.append(vector_size)
        return True

    monkeypatch.setattr(store, "_get_client", get_client)
    monkeypatch.setattr(store, "collection_exists", collection_exists)
    monkeypatch.setattr(store, "create_collection", create_collection)

    assert await store.upsert([{"id": "point-1", "vector": [0.1, 0.2], "payload": {}}]) is True
    assert created_sizes == [2]
