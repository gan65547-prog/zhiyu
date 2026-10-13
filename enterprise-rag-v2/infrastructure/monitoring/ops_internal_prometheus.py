"""
/internal/admin 运维内部接口的 Prometheus 指标（与现有自定义 /metrics JSON 并存）。
"""

from prometheus_client import Counter, Histogram

# 设计文档：ops_internal_api_latency_ms — Prometheus 惯例使用 _seconds
OPS_INTERNAL_API_LATENCY_SECONDS = Histogram(
    "ops_internal_api_latency_seconds",
    "Latency of /internal/admin requests",
    ["method", "route_group"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

OPS_INTERNAL_API_REQUESTS_TOTAL = Counter(
    "ops_internal_api_requests_total",
    "Total /internal/admin requests",
    ["method", "route_group", "status"],
)

INTERNAL_API_KEY_VERIFY_FAILED_TOTAL = Counter(
    "internal_api_key_verify_failed_total",
    "Invalid X-Internal-Api-Key attempts on /internal/admin",
)
