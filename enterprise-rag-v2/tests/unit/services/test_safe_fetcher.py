import pytest
import httpx

from services.impl.safe_fetcher import SafeFetcher, UnsafeUrlError, validate_content_type


@pytest.mark.asyncio
async def test_safe_fetcher_rejects_localhost_and_private_ip():
    fetcher = SafeFetcher()
    with pytest.raises(UnsafeUrlError):
        await fetcher._validate_url("http://localhost/internal")
    with pytest.raises(UnsafeUrlError):
        await fetcher._validate_url("http://127.0.0.1/internal")


@pytest.mark.asyncio
async def test_safe_fetcher_rejects_credentials_and_non_http_scheme():
    fetcher = SafeFetcher()
    with pytest.raises(UnsafeUrlError):
        await fetcher._validate_url("file:///etc/passwd")
    with pytest.raises(UnsafeUrlError):
        await fetcher._validate_url("https://user:password@example.com/a")


@pytest.mark.asyncio
async def test_safe_fetcher_propagates_upstream_timeout(monkeypatch):
    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("upstream timeout")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: TimeoutClient())
    fetcher = SafeFetcher(timeout_seconds=0.1)
    async def allow_url(_url):
        return None
    fetcher._validate_url = allow_url
    with pytest.raises(httpx.ReadTimeout, match="upstream timeout"):
        await fetcher.fetch("https://example.com/slow")


@pytest.mark.asyncio
async def test_safe_fetcher_propagates_upstream_http_error(monkeypatch):
    class ErrorClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            response = httpx.Response(503, request=httpx.Request("GET", "https://example.com/unavailable"))
            response.raise_for_status()
            return response

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: ErrorClient())
    fetcher = SafeFetcher()
    async def allow_url(_url):
        return None
    fetcher._validate_url = allow_url
    with pytest.raises(httpx.HTTPStatusError, match="503"):
        await fetcher.fetch("https://example.com/unavailable")


def test_content_type_validation_allows_known_types_and_rejects_unknown():
    assert validate_content_type("text/html; charset=utf-8", "report") == "text/html"
    assert validate_content_type("application/octet-stream", "report.pdf") == "application/pdf"
    with pytest.raises(UnsafeUrlError):
        validate_content_type("application/x-msdownload", "report.exe")
