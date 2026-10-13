"""受控外部 URL 获取器。

所有用户 URL 和后续外部研究来源必须复用此实现，禁止业务模块自行抓取。
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit

import httpx


REDIRECT_STATUSES = {301, 302, 303, 307, 308}
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "text/csv",
    "text/html",
    "text/markdown",
    "text/plain",
}


@dataclass(frozen=True)
class FetchedResource:
    url: str
    content: bytes
    content_type: str
    etag: str | None = None


class UnsafeUrlError(ValueError):
    """URL 不满足协议、解析或网络边界要求。"""


def validate_content_type(content_type: str | None, name: str = "") -> str:
    """校验素材类型，允许带参数的 MIME，并用扩展名兜底识别文本文件。"""
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    suffix = PurePosixPath(name.split("?", 1)[0]).suffix.lower()
    extension_types = {
        ".pdf": "application/pdf", ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv", ".html": "text/html", ".htm": "text/html", ".md": "text/markdown", ".txt": "text/plain",
    }
    if normalized in SUPPORTED_MIME_TYPES:
        return normalized
    if normalized in {"", "application/octet-stream"} and suffix in extension_types:
        return extension_types[suffix]
    raise UnsafeUrlError("不支持的素材 MIME 类型")


class SafeFetcher:
    def __init__(
        self,
        *,
        max_bytes: int = 20 * 1024 * 1024,
        max_redirects: int = 3,
        timeout_seconds: float = 20.0,
    ):
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.timeout = httpx.Timeout(timeout_seconds)

    async def _validate_host(self, hostname: str) -> None:
        if not hostname or hostname.lower() in {"localhost", "metadata.google.internal"}:
            raise UnsafeUrlError("禁止访问本地主机或云元数据地址")
        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo, hostname, None, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            raise UnsafeUrlError("URL 域名解析失败") from exc
        for address in {item[4][0] for item in addresses}:
            ip = ipaddress.ip_address(address)
            if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
                raise UnsafeUrlError("禁止访问内网、环回或保留地址")

    async def _validate_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or parts.username or parts.password:
            raise UnsafeUrlError("仅允许不带凭据的 http/https URL")
        await self._validate_host(parts.hostname or "")

    async def fetch(self, url: str, headers: dict[str, str] | None = None) -> FetchedResource:
        current_url = url
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            for redirect_count in range(self.max_redirects + 1):
                await self._validate_url(current_url)
                request_headers = {"Accept": "*/*", **(headers or {})}
                response = await client.get(current_url, headers=request_headers)
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location or redirect_count >= self.max_redirects:
                        raise UnsafeUrlError("URL 重定向次数超过限制")
                    current_url = urljoin(current_url, location)
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.max_bytes:
                    raise UnsafeUrlError("响应大小超过限制")
                content = response.content
                if len(content) > self.max_bytes:
                    raise UnsafeUrlError("响应大小超过限制")
                content_type = validate_content_type(
                    response.headers.get("content-type"), current_url
                )
                return FetchedResource(
                    url=current_url,
                    content=content,
                    content_type=content_type,
                    etag=response.headers.get("etag"),
                )
        raise UnsafeUrlError("URL 获取失败")
