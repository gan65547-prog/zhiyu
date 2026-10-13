from __future__ import annotations

import asyncio
import json
import logging
import time
from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.services.cache_service import READ_CACHE
from app.services.circuit_breaker import CIRCUIT_BREAKER

logger = logging.getLogger("ops_center.gateway")


class BusinessGateway:
    """封装 ops-center 到业务侧 internal admin 接口的调用。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def _cache_key(method: str, path: str, query_params: dict[str, object] | None) -> str:
        query = query_params or {}
        parts = [method.upper(), path, json.dumps(query, sort_keys=True, ensure_ascii=False)]
        return "|".join(parts)

    def _try_read_cache(self, method: str, path: str, query_params: dict[str, object] | None) -> dict | None:
        if method.upper() != "GET":
            return None
        return READ_CACHE.get(self._cache_key(method, path, query_params))

    async def request(
        self,
        method: str,
        path: str,
        *,
        query_params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        op_id: str | None = None,
        operator: str | None = None,
    ) -> dict:
        if not self.settings.internal_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"success": False, "error": {"code": "MISSING_INTERNAL_API_KEY", "message": "ops-center 未配置 INTERNAL_API_KEY"}},
            )

        request_id = str(uuid4())
        headers = {
            "X-Request-Id": request_id,
            "X-Internal-Api-Key": self.settings.internal_api_key,
            "X-Source-Env": self.settings.source_env,
        }
        if op_id:
            headers["X-Op-Id"] = op_id
        if operator:
            headers["X-Operator"] = operator

        url = f"{self.settings.business_base_url.rstrip('/')}/{path.lstrip('/')}"
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        retries = max(0, self.settings.gateway_read_retry_count) if method.upper() == "GET" else 0
        attempts = retries + 1
        last_exc: Exception | None = None
        response: httpx.Response | None = None
        cache_key = self._cache_key(method, path, query_params)

        if method.upper() == "GET" and CIRCUIT_BREAKER.is_open(path):
            cached = self._try_read_cache(method, path, query_params)
            if cached:
                return cached
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "success": False,
                    "error": {"code": "UPSTREAM_CIRCUIT_OPEN", "message": "上游服务熔断中，请稍后重试"},
                    "meta": {"request_id": str(uuid4())},
                },
            )

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(attempts):
                started_at = time.perf_counter()
                try:
                    response = await client.request(method, url, params=query_params, json=json_body, headers=headers)
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    logger.info(
                        "gateway_request",
                        extra={
                            "request_id": request_id,
                            "op_id": op_id,
                            "method": method.upper(),
                            "path": path,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "latency_ms": elapsed_ms,
                        },
                    )
                    # 读请求命中上游 5xx 时可重试
                    if method.upper() == "GET" and response.status_code >= 500 and attempt < attempts - 1:
                        await asyncio.sleep(self.settings.gateway_read_retry_backoff_seconds)
                        continue
                    break
                except (httpx.TimeoutException, httpx.HTTPError) as exc:
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    logger.warning(
                        "gateway_request_failed",
                        extra={
                            "request_id": request_id,
                            "op_id": op_id,
                            "method": method.upper(),
                            "path": path,
                            "attempt": attempt + 1,
                            "latency_ms": elapsed_ms,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    )
                    last_exc = exc
                    if method.upper() == "GET" and attempt < attempts - 1:
                        await asyncio.sleep(self.settings.gateway_read_retry_backoff_seconds)
                        continue
                    if isinstance(exc, httpx.TimeoutException):
                        if method.upper() == "GET":
                            CIRCUIT_BREAKER.record_failure(
                                path,
                                threshold=self.settings.circuit_breaker_failure_threshold,
                                window_seconds=self.settings.circuit_breaker_window_seconds,
                                open_seconds=self.settings.circuit_breaker_open_seconds,
                            )
                            cached = self._try_read_cache(method, path, query_params)
                            if cached:
                                return cached
                        raise HTTPException(
                            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                            detail={
                                "success": False,
                                "error": {"code": "UPSTREAM_TIMEOUT", "message": "业务侧内部接口超时"},
                                "meta": {"request_id": request_id},
                            },
                        ) from exc
                    if method.upper() == "GET":
                        CIRCUIT_BREAKER.record_failure(
                            path,
                            threshold=self.settings.circuit_breaker_failure_threshold,
                            window_seconds=self.settings.circuit_breaker_window_seconds,
                            open_seconds=self.settings.circuit_breaker_open_seconds,
                        )
                        cached = self._try_read_cache(method, path, query_params)
                        if cached:
                            return cached
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "success": False,
                            "error": {"code": "UPSTREAM_UNREACHABLE", "message": "无法连接业务侧内部接口"},
                            "meta": {"request_id": request_id},
                        },
                    ) from exc

        if response is None and last_exc is not None:
            if method.upper() == "GET":
                CIRCUIT_BREAKER.record_failure(
                    path,
                    threshold=self.settings.circuit_breaker_failure_threshold,
                    window_seconds=self.settings.circuit_breaker_window_seconds,
                    open_seconds=self.settings.circuit_breaker_open_seconds,
                )
                cached = self._try_read_cache(method, path, query_params)
                if cached:
                    return cached
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "success": False,
                    "error": {"code": "UPSTREAM_UNREACHABLE", "message": "无法连接业务侧内部接口"},
                    "meta": {"request_id": request_id},
                },
            ) from last_exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "success": False,
                    "error": {"code": "INVALID_UPSTREAM_RESPONSE", "message": "业务侧返回非 JSON"},
                    "meta": {"request_id": request_id, "status_code": response.status_code},
                },
            ) from exc

        if response.status_code >= 400:
            if method.upper() == "GET" and response.status_code >= 500:
                CIRCUIT_BREAKER.record_failure(
                    path,
                    threshold=self.settings.circuit_breaker_failure_threshold,
                    window_seconds=self.settings.circuit_breaker_window_seconds,
                    open_seconds=self.settings.circuit_breaker_open_seconds,
                )
                cached = self._try_read_cache(method, path, query_params)
                if cached:
                    return cached
            raise HTTPException(status_code=response.status_code, detail=payload)
        if method.upper() == "GET":
            CIRCUIT_BREAKER.record_success(path)
            READ_CACHE.set(cache_key, payload, self.settings.read_cache_ttl_seconds)
        return payload
