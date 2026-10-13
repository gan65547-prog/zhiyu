import re
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

import services.impl.content_connector_registry as connector_module
from services.impl.content_connector_registry import (
    ContentConnectorRegistry,
    WeChatPublisher,
)


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, responder, calls):
        self._responder = responder
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, *, params=None, headers=None):
        self._calls.append({"method": "GET", "url": url, "params": params, "payload": None})
        return self._responder("GET", url)

    async def post(self, url, *, params=None, json=None, headers=None):
        self._calls.append({"method": "POST", "url": url, "params": params, "payload": json})
        return self._responder("POST", url)


@pytest.fixture
def wechat_calls(monkeypatch):
    monkeypatch.setattr(WeChatPublisher, "_token_cache", {})
    calls: list[dict] = []
    return calls


def _patch_client(monkeypatch, calls, responder):
    monkeypatch.setattr(
        connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient(responder, calls)
    )


def _credentials():
    return {"app_id": "wx-app", "app_secret": "wx-secret", "thumb_media_id": "THUMB-1"}


TOKEN_URL = WeChatPublisher.token_endpoint
DRAFT_URL = WeChatPublisher.draft_endpoint
SUBMIT_URL = WeChatPublisher.publish_endpoint
STATUS_URL = WeChatPublisher.publish_status_endpoint
METRICS_URL = WeChatPublisher.metrics_endpoint


@pytest.mark.asyncio
async def test_credentials_validates_token(monkeypatch, wechat_calls):
    _patch_client(
        monkeypatch,
        wechat_calls,
        lambda method, url: FakeResponse(body={"access_token": "tk-1", "expires_in": 7200}),
    )
    publisher = WeChatPublisher()
    result = await publisher.test_credentials(credentials=_credentials())

    assert result["status"] == "configured"
    assert wechat_calls[0]["url"] == TOKEN_URL
    assert wechat_calls[0]["params"]["appid"] == "wx-app"
    assert wechat_calls[0]["params"]["secret"] == "wx-secret"


@pytest.mark.asyncio
async def test_credentials_rejects_bad_secret(monkeypatch, wechat_calls):
    _patch_client(
        monkeypatch,
        wechat_calls,
        lambda method, url: FakeResponse(body={"errcode": 40125, "errmsg": "invalid appsecret"}),
    )
    publisher = WeChatPublisher()
    result = await publisher.test_credentials(credentials=_credentials())

    assert result["status"] == "failed"
    assert result["retryable"] is False


@pytest.mark.asyncio
async def test_dispatch_two_phase_publish(monkeypatch, wechat_calls):
    def responder(method, url):
        if url == TOKEN_URL:
            return FakeResponse(body={"access_token": "tk-1", "expires_in": 7200})
        if url == DRAFT_URL:
            return FakeResponse(body={"media_id": "MEDIA-1"})
        if url == SUBMIT_URL:
            return FakeResponse(body={"publish_id": "PUB-1"})
        raise AssertionError(f"意外请求 {url}")

    _patch_client(monkeypatch, wechat_calls, responder)
    publisher = WeChatPublisher()
    draft = SimpleNamespace(title="标题", body="## 小节\n\n正文 **加粗** 内容")
    result = await publisher.dispatch(draft=draft, record=SimpleNamespace(id="r1"), credentials=_credentials())

    assert result.status == "published"
    assert result.external_id == "PUB-1"
    assert result.response["draft_id"] == "MEDIA-1"
    assert result.response["pending_review"] is True
    draft_call = next(call for call in wechat_calls if call["url"] == DRAFT_URL)
    article = draft_call["payload"]["articles"][0]
    assert article["title"] == "标题"
    assert article["thumb_media_id"] == "THUMB-1"
    assert "<h2>小节</h2>" in article["content"]
    assert "<p>正文 <strong>加粗</strong> 内容</p>" in article["content"]
    submit_call = next(call for call in wechat_calls if call["url"] == SUBMIT_URL)
    assert submit_call["payload"] == {"media_id": "MEDIA-1"}


@pytest.mark.asyncio
async def test_dispatch_refreshes_token_once_on_40001(monkeypatch, wechat_calls):
    token_requests = {"count": 0}

    def responder(method, url):
        if url == TOKEN_URL:
            token_requests["count"] += 1
            return FakeResponse(body={"access_token": f"tk-{token_requests['count']}", "expires_in": 7200})
        if url == DRAFT_URL:
            if token_requests["count"] < 2:
                return FakeResponse(body={"errcode": 40001, "errmsg": "invalid credential"})
            return FakeResponse(body={"media_id": "MEDIA-1"})
        if url == SUBMIT_URL:
            return FakeResponse(body={"publish_id": "PUB-1"})
        raise AssertionError(f"意外请求 {url}")

    _patch_client(monkeypatch, wechat_calls, responder)
    publisher = WeChatPublisher()
    draft = SimpleNamespace(title="标题", body="正文")
    result = await publisher.dispatch(draft=draft, record=SimpleNamespace(id="r1"), credentials=_credentials())

    assert result.status == "published"
    assert token_requests["count"] == 2
    draft_calls = [call for call in wechat_calls if call["url"] == DRAFT_URL]
    assert len(draft_calls) == 2
    assert draft_calls[0]["params"]["access_token"] == "tk-1"
    assert draft_calls[1]["params"]["access_token"] == "tk-2"


@pytest.mark.asyncio
async def test_dispatch_rate_limit_is_retryable(monkeypatch, wechat_calls):
    def responder(method, url):
        if url == TOKEN_URL:
            return FakeResponse(body={"access_token": "tk-1", "expires_in": 7200})
        if url == DRAFT_URL:
            return FakeResponse(body={"errcode": 45009, "errmsg": "freq limit"})
        raise AssertionError(f"意外请求 {url}")

    _patch_client(monkeypatch, wechat_calls, responder)
    publisher = WeChatPublisher()
    draft = SimpleNamespace(title="标题", body="正文")
    result = await publisher.dispatch(draft=draft, record=SimpleNamespace(id="r1"), credentials=_credentials())

    assert result.status == "failed"
    assert result.response["retryable"] is True


@pytest.mark.asyncio
async def test_dispatch_requires_thumb_media_id(monkeypatch, wechat_calls):
    _patch_client(monkeypatch, wechat_calls, lambda method, url: FakeResponse(body={}))
    publisher = WeChatPublisher()
    creds = {"app_id": "wx-app", "app_secret": "wx-secret"}
    draft = SimpleNamespace(title="标题", body="正文")
    result = await publisher.dispatch(draft=draft, record=SimpleNamespace(id="r1"), credentials=creds)

    assert result.status == "failed"
    assert result.response["retryable"] is False
    assert wechat_calls == []


@pytest.mark.asyncio
async def test_fetch_metrics_maps_datacube_fields(monkeypatch, wechat_calls):
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    def responder(method, url):
        if url == TOKEN_URL:
            return FakeResponse(body={"access_token": "tk-1", "expires_in": 7200})
        if url == STATUS_URL:
            return FakeResponse(body={"publish_status": {"article_detail": {"item": [{"article": {"article_url": "https://mp.weixin.qq.com/s/abc?x=1"}}]}}})
        if url == METRICS_URL:
            return FakeResponse(body={"list": [{"url": "https://mp.weixin.qq.com/s/abc?from=feed", "int_page_read_count": 120, "ori_page_read_count": 9, "int_page_share_count": 4, "msgid": 77}]})
        raise AssertionError(f"意外请求 {url}")

    _patch_client(monkeypatch, wechat_calls, responder)
    publisher = WeChatPublisher()
    result = await publisher.fetch_metrics(external_id="PUB-1", credentials=_credentials())

    assert result["status"] == "configured"
    assert result["collected_at"] == yesterday
    assert result["metric"]["impressions"] == 120
    assert result["metric"]["clicks"] == 9
    assert result["metric"]["shares"] == 4
    metrics_call = next(call for call in wechat_calls if call["url"] == METRICS_URL)
    assert metrics_call["payload"] == {"begin_date": yesterday, "end_date": yesterday}


@pytest.mark.asyncio
async def test_fetch_metrics_pending_review_is_retryable(monkeypatch, wechat_calls):
    def responder(method, url):
        if url == TOKEN_URL:
            return FakeResponse(body={"access_token": "tk-1", "expires_in": 7200})
        if url == STATUS_URL:
            return FakeResponse(body={"publish_status": {"article_detail": {"item": []}}})
        raise AssertionError(f"意外请求 {url}")

    _patch_client(monkeypatch, wechat_calls, responder)
    publisher = WeChatPublisher()
    result = await publisher.fetch_metrics(external_id="PUB-1", credentials=_credentials())

    assert result["status"] == "failed"
    assert result["retryable"] is True
    assert all(call["url"] != METRICS_URL for call in wechat_calls)


def test_registry_serves_wechat_and_keeps_other_pending():
    registry = ContentConnectorRegistry()
    assert isinstance(registry.get("wechat"), WeChatPublisher)
    described = {item["key"]: item for item in registry.describe()}
    assert described["wechat"]["status"] == "available"
    assert described["wechat"]["supports_metric_sync"] is True
    assert {"douyin", "zhihu"} == {key for key, item in described.items() if item["status"] == "pending_adapter"}


def test_markdown_to_html_escapes_and_keeps_lists():
    content = WeChatPublisher._markdown_to_html("- 条目 <b>x</b>\n\n段落 **重点**")
    assert "<ul><li>条目 &lt;b&gt;x&lt;/b&gt;</li></ul>" in content
    assert "<p>段落 <strong>重点</strong></p>" in content
    assert not re.search(r"<b>x</b>", content)
