import json

import pytest
import httpx

from core.interfaces.rag_engine import RetrievedDocument
from core.rag.llm_provider import (
    DeepSeekProvider,
    LLMProviderFactory,
    OllamaLLMProvider,
    OpenAIProvider,
)


def test_llm_provider_factory_only_creates_allowlisted_providers():
    assert isinstance(LLMProviderFactory.create("ollama"), OllamaLLMProvider)
    assert isinstance(LLMProviderFactory.create("deepseek"), DeepSeekProvider)
    assert isinstance(LLMProviderFactory.create("openai"), OpenAIProvider)
    with pytest.raises(ValueError, match="不支持"):
        LLMProviderFactory.create("untrusted-provider")


@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_chat_completion(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "可追溯回答"}}]}

    class FakeClient:
        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    provider = OpenAIProvider(api_key="test-key", model="test-model", base_url="https://example.com")
    monkeypatch.setattr(provider, "_get_client", lambda: _async_value(FakeClient()))
    answer = await provider.generate(
        "问题",
        [RetrievedDocument(id="1", content="来源内容", metadata={}, score=1.0, document_id="1", document_name="来源", chunk_index=0)],
    )
    assert answer == "可追溯回答"
    assert provider.base_url == "https://example.com/v1"


@pytest.mark.asyncio
async def test_openai_compatible_provider_remote_http_contract_and_stream(monkeypatch):
    requests = []

    async def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        if payload["stream"]:
            body = 'data: {"choices":[{"delta":{"content":"流"}}]}\n\ndata: {"choices":[{"delta":{"content":"式"}}]}\n\ndata: [DONE]\n\n'.encode()
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "远程回答"}}]})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer remote-test-key", "Content-Type": "application/json"},
    )
    provider = OpenAIProvider(api_key="remote-test-key", model="remote-model", base_url="https://llm.example.test")

    async def get_client():
        return client

    monkeypatch.setattr(provider, "_get_client", get_client)
    document = RetrievedDocument(id="1", content="来源内容", metadata={}, score=1.0, document_id="1", document_name="来源", chunk_index=0)
    assert await provider.generate("问题", [document]) == "远程回答"
    streamed = "".join([part async for part in provider.generate_stream("问题", [document])])
    assert streamed == "流式"
    assert len(requests) == 2
    assert all(request.url.path == "/v1/chat/completions" for request in requests)
    assert all(request.headers["authorization"] == "Bearer remote-test-key" for request in requests)
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_provider_returns_ranked_evidence_when_remote_unavailable(monkeypatch):
    class FakeResponse:
        status_code = 503
        text = "service unavailable"

    class FakeClient:
        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    provider = OpenAIProvider(api_key="test-key", model="test-model", base_url="https://example.com")
    monkeypatch.setattr(provider, "_get_client", lambda: _async_value(FakeClient()))
    documents = [
        RetrievedDocument(id="1", content="无关内容", metadata={}, score=0.2, document_id="1", document_name="低相关来源", chunk_index=0),
        RetrievedDocument(id="2", content="知识库支持截图 OCR，并且会在完成后建立索引。", metadata={}, score=0.4, document_id="2", document_name="OCR 指南", chunk_index=1),
    ]

    answer = await provider.generate("截图 OCR", documents)

    assert "模型服务当前不可用" in answer
    assert "OCR 指南" in answer
    assert answer.index("OCR 指南") < answer.index("低相关来源")


async def _async_value(value):
    return value
