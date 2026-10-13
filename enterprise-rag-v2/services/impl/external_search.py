"""受控外部搜索适配器。

搜索服务只返回候选 URL；正文仍必须交给 SafeFetcher 获取，避免搜索适配器绕过
SSRF、重定向、大小和 MIME 约束。未配置端点时明确返回不可用，不自动访问未知服务。
"""

import json
import os
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx

from services.impl.safe_fetcher import SafeFetcher


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str


class ExternalSearchUnavailable(RuntimeError):
    """外部搜索未配置或暂时不可用。"""


class ExternalSearchProvider:
    def __init__(self, fetcher: SafeFetcher | None = None, max_results: int = 5):
        self.fetcher = fetcher or SafeFetcher(max_bytes=2 * 1024 * 1024)
        self.max_results = max_results
        self.endpoint = os.getenv("RESEARCH_SEARCH_ENDPOINT", "").strip()
        self.api_key = os.getenv("RESEARCH_SEARCH_API_KEY", "").strip()

    async def search(self, query: str) -> list[SearchResult]:
        if not self.endpoint:
            raise ExternalSearchUnavailable("未配置 RESEARCH_SEARCH_ENDPOINT")
        url = self.endpoint.replace("{query}", quote_plus(query), 1)
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = await self.fetcher.fetch(url, headers=headers)
        except httpx.HTTPError as exc:
            raise ExternalSearchUnavailable("外部搜索服务请求失败") from exc
        try:
            payload = json.loads(response.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalSearchUnavailable("外部搜索响应不是有效 JSON") from exc
        candidates = payload.get("results", payload.get("organic_results", []))
        if not isinstance(candidates, list):
            raise ExternalSearchUnavailable("外部搜索响应缺少结果列表")
        results: list[SearchResult] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            result_url = str(item.get("url") or item.get("link") or "").strip()
            if not result_url:
                continue
            results.append(SearchResult(
                url=result_url,
                title=str(item.get("title") or result_url)[:255],
                snippet=str(item.get("snippet") or item.get("description") or "")[:1000],
            ))
            if len(results) >= self.max_results:
                break
        return results
