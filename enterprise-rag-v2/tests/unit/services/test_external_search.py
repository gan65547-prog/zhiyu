import json

import pytest
import httpx

from services.impl.external_search import ExternalSearchProvider, ExternalSearchUnavailable
from services.impl.safe_fetcher import FetchedResource


class FakeFetcher:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    async def fetch(self, url: str, headers=None):
        self.calls.append((url, headers or {}))
        return FetchedResource(
            url=url, content=json.dumps(self.payload).encode(), content_type="application/json"
        )


@pytest.mark.asyncio
async def test_external_search_parses_configured_results(monkeypatch):
    monkeypatch.setenv("RESEARCH_SEARCH_ENDPOINT", "https://search.example.test?q={query}")
    monkeypatch.setenv("RESEARCH_SEARCH_API_KEY", "secret")
    fetcher = FakeFetcher({"results": [{"url": "https://example.com/a", "title": "行业报告", "snippet": "摘要"}]})
    results = await ExternalSearchProvider(fetcher=fetcher).search("智能制造")
    assert results[0].url == "https://example.com/a"
    assert "q=%E6%99%BA%E8%83%BD%E5%88%B6%E9%80%A0" in fetcher.calls[0][0]
    assert fetcher.calls[0][1]["Authorization"] == "Bearer secret"


@pytest.mark.asyncio
async def test_external_search_requires_explicit_endpoint(monkeypatch):
    monkeypatch.delenv("RESEARCH_SEARCH_ENDPOINT", raising=False)
    with pytest.raises(ExternalSearchUnavailable):
        await ExternalSearchProvider().search("行业趋势")


@pytest.mark.asyncio
async def test_external_search_http_failure_is_explicitly_unavailable(monkeypatch):
    monkeypatch.setenv("RESEARCH_SEARCH_ENDPOINT", "https://search.example.test?q={query}")

    class FailingFetcher:
        async def fetch(self, _url: str, headers=None):
            raise httpx.ReadTimeout("search timeout")

    with pytest.raises(ExternalSearchUnavailable):
        await ExternalSearchProvider(fetcher=FailingFetcher()).search("行业趋势")
