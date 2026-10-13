"""
记录 /internal/admin 请求的 Prometheus 指标。
"""

from __future__ import annotations

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from infrastructure.monitoring.ops_internal_prometheus import (
    OPS_INTERNAL_API_LATENCY_SECONDS,
    OPS_INTERNAL_API_REQUESTS_TOTAL,
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def normalize_internal_admin_route(path: str) -> str:
    """降低基数：将路径中的 UUID 替换为 {id}。"""
    return _UUID_RE.sub("{id}", path)


class InternalAdminMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/internal/admin"):
            return await call_next(request)

        route_group = normalize_internal_admin_route(request.url.path)
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        status_label = "success" if response.status_code < 400 else "error"
        OPS_INTERNAL_API_LATENCY_SECONDS.labels(request.method, route_group).observe(elapsed)
        OPS_INTERNAL_API_REQUESTS_TOTAL.labels(
            request.method, route_group, status_label
        ).inc()
        return response
