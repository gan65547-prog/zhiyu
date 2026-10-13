"""内容发布连接器注册表；只允许显式注册的适配器执行。"""

import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

from services.interfaces.content_publisher import ConnectorResult, ContentPublisher
from services.impl.safe_fetcher import SafeFetcher


PENDING_CONNECTORS = (
    {"key": "douyin", "label": "抖音"},
    {"key": "zhihu", "label": "知乎"},
)


class ManualContentPublisher:
    key = "manual"
    label = "人工确认"
    requires_credentials = False

    async def dispatch(self, *, draft: Any, record: Any, credentials: dict[str, Any] | None = None) -> ConnectorResult:
        return ConnectorResult(
            status="ready",
            response={"connector": self.key, "requires_manual_confirmation": True},
        )


class WebsiteWebhookPublisher:
    """通过用户配置的 HTTPS Webhook 发布网站内容。

    这是一个真实的通用网站适配器，不假设具体 CMS。平台私有连接器仍需
    独立实现；Webhook 请求不携带凭据本身，只发送审核通过的内容和发布记录。
    """

    key = "website"
    label = "网站 Webhook"
    requires_credentials = True

    async def dispatch(self, *, draft: Any, record: Any, credentials: dict[str, Any] | None = None) -> ConnectorResult:
        webhook_url = str((credentials or {}).get("webhook_url") or "").strip()
        if not webhook_url:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "网站 Webhook 凭据缺少 webhook_url", "retryable": False})
        if urlsplit(webhook_url).scheme != "https":
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "网站 Webhook 只允许 HTTPS 地址", "retryable": False})

        raw_headers = (credentials or {}).get("headers") or {}
        if not isinstance(raw_headers, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in raw_headers.items()):
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "网站 Webhook headers 必须是字符串键值对象", "retryable": False})
        headers = {str(key): str(value) for key, value in raw_headers.items()}
        headers.setdefault("Content-Type", "application/json")
        payload = {
            "event": "content.publish",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "draft": {"id": str(draft.id), "title": str(draft.title), "body": str(draft.body)},
            "publish": {"id": str(record.id), "platform": self.key},
        }
        try:
            await SafeFetcher()._validate_url(webhook_url)
            timeout_seconds = float((credentials or {}).get("timeout_seconds", 15))
            timeout_seconds = min(max(timeout_seconds, 1), 30)
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=False) as client:
                response = await client.post(webhook_url, headers=headers, json=payload)
            response_body: dict[str, Any] = {}
            try:
                parsed = response.json()
                if isinstance(parsed, dict): response_body = parsed
            except (ValueError, json.JSONDecodeError):
                pass
            if not 200 <= response.status_code < 300:
                return ConnectorResult(status="failed", response={"connector": self.key, "status_code": response.status_code, "error": f"网站 Webhook 返回 HTTP {response.status_code}", "retryable": response.status_code == 429 or response.status_code >= 500})
            external_id = response_body.get("external_id") or response_body.get("id")
            return ConnectorResult(status="published", external_id=str(external_id) if external_id else None, response={"connector": self.key, "status_code": response.status_code, "external_id": external_id, "response": response_body})
        except Exception as exc:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": f"网站 Webhook 请求失败：{str(exc)[:500]}", "retryable": True})


class XPostPublisher:
    """使用 X API v2 用户上下文发布短帖。

    凭据只接受 OAuth 用户访问令牌；API 地址固定为官方域名，避免把凭据
    配置变成任意外部请求入口。指标同步与 OAuth 授权页仍由后续迭代补齐。
    """

    key = "x"
    label = "X / 短帖"
    requires_credentials = True
    endpoint = "https://api.x.com/2/tweets"
    profile_endpoint = "https://api.x.com/2/users/me"
    metrics_endpoint = "https://api.x.com/2/tweets/{}"

    @staticmethod
    def _token(credentials: dict[str, Any] | None) -> str:
        value = (credentials or {}).get("access_token") or (credentials or {}).get("oauth2_access_token")
        return str(value).strip() if value else ""

    @staticmethod
    def _timeout(credentials: dict[str, Any] | None) -> float:
        try:
            value = float((credentials or {}).get("timeout_seconds", 15))
        except (TypeError, ValueError):
            value = 15
        return min(max(value, 1), 30)

    @staticmethod
    def _response_body(response: Any) -> dict[str, Any]:
        try:
            parsed = response.json()
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    async def test_credentials(self, *, credentials: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._token(credentials)
        if not token:
            return {"status": "failed", "message": "X 凭据缺少 OAuth 用户访问令牌", "retryable": False}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout(credentials)), follow_redirects=False) as client:
                response = await client.get(self.profile_endpoint, headers={"Authorization": f"Bearer {token}"})
            if not 200 <= response.status_code < 300:
                return {"status": "failed", "message": f"X 凭据验证返回 HTTP {response.status_code}", "retryable": response.status_code == 429 or response.status_code >= 500}
            body = self._response_body(response)
            return {"status": "configured", "message": "X OAuth 用户凭据验证通过", "external_user_id": (body.get("data") or {}).get("id")}
        except Exception:
            return {"status": "failed", "message": "X 凭据验证请求失败", "retryable": True}

    async def dispatch(self, *, draft: Any, record: Any, credentials: dict[str, Any] | None = None) -> ConnectorResult:
        token = self._token(credentials)
        if not token:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "X 凭据缺少 OAuth 用户访问令牌", "retryable": False})
        text = str(draft.title or "").strip()
        body = str(draft.body or "").strip()
        if body:
            text = f"{text}\n\n{body}" if text else body
        if not text or len(text) > 280:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "X 短帖内容必须为 1 至 280 个字符", "retryable": False})
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout(credentials)), follow_redirects=False) as client:
                response = await client.post(self.endpoint, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"text": text})
            body_json = self._response_body(response)
            if not 200 <= response.status_code < 300:
                return ConnectorResult(status="failed", response={"connector": self.key, "status_code": response.status_code, "error": f"X API 返回 HTTP {response.status_code}", "retryable": response.status_code == 429 or response.status_code >= 500})
            external_id = (body_json.get("data") or {}).get("id")
            return ConnectorResult(status="published", external_id=str(external_id) if external_id else None, response={"connector": self.key, "status_code": response.status_code, "external_id": external_id})
        except Exception:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "X API 发布请求失败", "retryable": True})

    async def fetch_metrics(self, *, external_id: str, credentials: dict[str, Any] | None = None) -> dict[str, Any]:
        """读取已发布短帖的公开指标，供异步指标同步任务使用。"""
        token = self._token(credentials)
        if not token:
            return {"status": "failed", "message": "X 凭据缺少 OAuth 用户访问令牌", "retryable": False}
        post_id = str(external_id or "").strip()
        if not post_id or not post_id.isdigit():
            return {"status": "failed", "message": "X 发布记录缺少有效的帖子 ID", "retryable": False}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout(credentials)), follow_redirects=False) as client:
                response = await client.get(
                    self.metrics_endpoint.format(post_id),
                    headers={"Authorization": f"Bearer {token}"},
                    params={"tweet.fields": "public_metrics,created_at"},
                )
            if not 200 <= response.status_code < 300:
                return {"status": "failed", "message": f"X 指标接口返回 HTTP {response.status_code}", "retryable": response.status_code == 429 or response.status_code >= 500}
            data = self._response_body(response).get("data") or {}
            metrics = data.get("public_metrics") or {}
            return {
                "status": "configured",
                "collected_at": data.get("created_at"),
                "metric": {
                    "impressions": int(metrics.get("impression_count", 0) or 0),
                    "clicks": 0,
                    "likes": int(metrics.get("like_count", 0) or 0),
                    "comments": int(metrics.get("reply_count", 0) or 0),
                    "shares": int(metrics.get("retweet_count", 0) or 0) + int(metrics.get("quote_count", 0) or 0),
                    "raw": {"source": "x_api_v2", "public_metrics": metrics},
                },
            }
        except Exception:
            return {"status": "failed", "message": "X 指标请求失败", "retryable": True}


class WeChatPublisher:
    """微信公众号图文发布适配器（cgi-bin draft + freepublish）。

    凭据：app_id/app_secret/thumb_media_id（默认封面永久素材）。发布为
    两段式：draft/add 建图文草稿 → freepublish/submit 提交发布；平台
    异步审核期间文章不可见，publish_id 作为 external_id，指标走
    datacube（T+1 延迟）。
    """

    key = "wechat"
    label = "微信公众号"
    requires_credentials = True
    api_base = "https://api.weixin.qq.com"
    token_endpoint = "https://api.weixin.qq.com/cgi-bin/token"
    draft_endpoint = "https://api.weixin.qq.com/cgi-bin/draft/add"
    publish_endpoint = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
    publish_status_endpoint = "https://api.weixin.qq.com/cgi-bin/freepublish/get"
    metrics_endpoint = "https://api.weixin.qq.com/datacube/getarticletotal"
    _TOKEN_REFRESH_ERRCODES = {40001, 40014, 42001}
    _RETRYABLE_ERRCODES = {-1, 45009}
    _token_cache: dict[str, tuple[str, float]] = {}

    @staticmethod
    def _timeout(credentials: dict[str, Any] | None) -> float:
        try:
            value = float((credentials or {}).get("timeout_seconds", 15))
        except (TypeError, ValueError):
            value = 15
        return min(max(value, 1), 30)

    @staticmethod
    def _response_body(response: Any) -> dict[str, Any]:
        try:
            parsed = response.json()
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _inline(text: str) -> str:
        escaped = html.escape(text, quote=False)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    @classmethod
    def _markdown_to_html(cls, markdown: str) -> str:
        lines: list[str] = []
        in_list = False

        def close_list() -> None:
            nonlocal in_list
            if in_list:
                lines.append("</ul>")
                in_list = False

        for raw in markdown.replace("\r\n", "\n").split("\n"):
            line = raw.strip()
            if not line:
                close_list()
            elif line.startswith("# "):
                close_list()
                lines.append(f"<h1>{cls._inline(line[2:])}</h1>")
            elif line.startswith("## "):
                close_list()
                lines.append(f"<h2>{cls._inline(line[3:])}</h2>")
            elif line.startswith("### "):
                close_list()
                lines.append(f"<h3>{cls._inline(line[4:])}</h3>")
            elif line.startswith("- ") or line.startswith("* "):
                if not in_list:
                    lines.append("<ul>")
                    in_list = True
                lines.append(f"<li>{cls._inline(line[2:])}</li>")
            else:
                close_list()
                lines.append(f"<p>{cls._inline(line)}</p>")
        close_list()
        return "".join(lines)

    async def _access_token(self, credentials: dict[str, Any], client: Any, *, force: bool = False) -> tuple[str, str]:
        app_id = str(credentials.get("app_id") or "").strip()
        app_secret = str(credentials.get("app_secret") or "").strip()
        if not app_id or not app_secret:
            return "", "公众号凭据缺少 app_id/app_secret"
        cached = self._token_cache.get(app_id)
        now = time.time()
        if not force and cached and cached[1] > now:
            return cached[0], ""
        response = await client.get(
            self.token_endpoint,
            params={"appid": app_id, "secret": app_secret, "grant_type": "client_credential"},
        )
        body = self._response_body(response)
        if not 200 <= response.status_code < 300 or body.get("errcode") not in (None, 0):
            return "", f"获取 access_token 失败：HTTP {response.status_code} errcode={body.get('errcode')}"
        token = str(body.get("access_token") or "")
        if not token:
            return "", "获取 access_token 失败：响应缺少 access_token"
        expires_in = int(body.get("expires_in", 7200) or 7200)
        self._token_cache[app_id] = (token, now + max(expires_in - 300, 60))
        return token, ""

    async def _api_call(
        self, *, path: str, credentials: dict[str, Any], payload: dict[str, Any] | None = None, force_token: bool = False
    ) -> tuple[dict[str, Any] | None, str, bool]:
        """返回 (body, error, retryable)；body 仅在 error 为空时有效。"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout(credentials)), follow_redirects=False) as client:
                token, token_error = await self._access_token(credentials, client, force=force_token)
                if token_error:
                    return None, token_error, False
                response = await client.post(
                    f"{self.api_base}{path}", params={"access_token": token}, json=payload or {}
                )
            body = self._response_body(response)
            if not 200 <= response.status_code < 300:
                retryable = response.status_code == 429 or response.status_code >= 500
                return None, f"公众号接口返回 HTTP {response.status_code}", retryable
            errcode = body.get("errcode")
            if errcode in (None, 0):
                return body, "", False
            if errcode in self._TOKEN_REFRESH_ERRCODES and not force_token:
                body, error, _ = await self._api_call(path=path, credentials=credentials, payload=payload, force_token=True)
                return body, error, False
            return None, f"公众号接口错误 errcode={errcode} errmsg={body.get('errmsg')}", errcode in self._RETRYABLE_ERRCODES
        except Exception as exc:
            return None, f"公众号接口请求失败：{str(exc)[:300]}", True

    async def test_credentials(self, *, credentials: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout(credentials)), follow_redirects=False) as client:
                _, token_error = await self._access_token(credentials or {}, client, force=True)
            if token_error:
                return {"status": "failed", "message": token_error, "retryable": False}
            return {"status": "configured", "message": "公众号凭据验证通过"}
        except Exception:
            return {"status": "failed", "message": "公众号凭据验证请求失败", "retryable": True}

    async def dispatch(self, *, draft: Any, record: Any, credentials: dict[str, Any] | None = None) -> ConnectorResult:
        creds = credentials or {}
        thumb_media_id = str(creds.get("thumb_media_id") or "").strip()
        if not thumb_media_id:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "公众号凭据缺少 thumb_media_id（默认封面永久素材）", "retryable": False})
        title = str(draft.title or "").strip()
        body_markdown = str(draft.body or "").strip()
        if not title or not body_markdown:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "公众号图文需要非空标题和正文", "retryable": False})
        draft_payload = {
            "articles": [{
                "title": title[:64],
                "content": self._markdown_to_html(body_markdown),
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }]
        }
        draft_body, error, retryable = await self._api_call(path="/cgi-bin/draft/add", credentials=creds, payload=draft_payload)
        if error:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": error, "retryable": retryable})
        media_id = str(draft_body.get("media_id") or "")
        if not media_id:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "草稿创建响应缺少 media_id", "retryable": False})
        publish_body, error, retryable = await self._api_call(path="/cgi-bin/freepublish/submit", credentials=creds, payload={"media_id": media_id})
        if error:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": error, "retryable": retryable, "draft_id": media_id})
        publish_id = str(publish_body.get("publish_id") or "")
        if not publish_id:
            return ConnectorResult(status="failed", response={"connector": self.key, "error": "发布提交响应缺少 publish_id", "retryable": False, "draft_id": media_id})
        return ConnectorResult(
            status="published",
            external_id=publish_id,
            response={"connector": self.key, "draft_id": media_id, "publish_id": publish_id, "pending_review": True},
        )

    @staticmethod
    def _first_article_url(publish_body: dict[str, Any]) -> str:
        items = ((publish_body.get("publish_status") or {}).get("article_detail") or {}).get("item") or []
        for item in items:
            url = str((item.get("article") or {}).get("article_url") or "")
            if url:
                return url
        return ""

    @staticmethod
    def _datacube_metric(entry: dict[str, Any], day: str) -> dict[str, Any]:
        return {
            "status": "configured",
            "collected_at": day,
            "metric": {
                "impressions": int(entry.get("int_page_read_count", 0) or 0),
                "clicks": int(entry.get("ori_page_read_count", 0) or 0),
                "likes": 0,
                "comments": 0,
                "shares": int(entry.get("int_page_share_count", 0) or 0),
                "raw": {"source": "wechat_datacube", "ref_date": day, "msgid": entry.get("msgid")},
            },
        }

    async def fetch_metrics(self, *, external_id: str, credentials: dict[str, Any] | None = None) -> dict[str, Any]:
        creds = credentials or {}
        publish_id = str(external_id or "").strip()
        if not publish_id:
            return {"status": "failed", "message": "公众号发布记录缺少 publish_id", "retryable": False}
        publish_body, error, retryable = await self._api_call(path="/cgi-bin/freepublish/get", credentials=creds, payload={"publish_id": publish_id})
        if error:
            return {"status": "failed", "message": error, "retryable": retryable}
        article_url = self._first_article_url(publish_body)
        if not article_url:
            return {"status": "failed", "message": "文章尚未发布完成（平台审核中）", "retryable": True}
        day = (date.today() - timedelta(days=1)).isoformat()
        data_body, error, retryable = await self._api_call(
            path="/datacube/getarticletotal", credentials=creds, payload={"begin_date": day, "end_date": day}
        )
        if error:
            return {"status": "failed", "message": error, "retryable": retryable}
        for entry in data_body.get("list") or []:
            if str(entry.get("url") or "").split("?")[0] == article_url.split("?")[0]:
                return self._datacube_metric(entry, day)
        return {"status": "failed", "message": "datacube 暂无该文章当日数据（T+1 延迟）", "retryable": True}


class ContentConnectorRegistry:
    def __init__(self, connectors: list[ContentPublisher] | None = None):
        self._connectors = {connector.key: connector for connector in (connectors or [ManualContentPublisher(), WebsiteWebhookPublisher(), XPostPublisher(), WeChatPublisher()])}

    def get(self, platform: str) -> ContentPublisher | None:
        return self._connectors.get(platform.strip().lower())

    def describe(self) -> list[dict[str, Any]]:
        descriptions = [{"key": connector.key, "label": connector.label, "status": "available", "requires_credentials": bool(getattr(connector, "requires_credentials", False)), "supports_metric_sync": callable(getattr(connector, "fetch_metrics", None))} for connector in self._connectors.values()]
        registered = {item["key"] for item in descriptions}
        descriptions.extend({**item, "status": "pending_adapter", "requires_credentials": True, "supports_metric_sync": False} for item in PENDING_CONNECTORS if item["key"] not in registered)
        return descriptions
