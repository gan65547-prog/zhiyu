from __future__ import annotations

from typing import Any


async def run_startup_prewarm(gateway_factory=None) -> dict[str, Any]:
    """
    启动预热高频只读接口缓存。
    失败不阻断启动，只返回状态供 health 暴露。
    """
    if gateway_factory is None:
        from app.services.business_gateway import BusinessGateway

        gateway_factory = BusinessGateway

    gateway = gateway_factory()
    targets: list[tuple[str, dict[str, object] | None]] = [
        ("/internal/admin/tenants", {"page": 1, "page_size": 20}),
        ("/internal/admin/operations", {"page": 1, "page_size": 20}),
        ("/internal/admin/audit/logs", {"page": 1, "page_size": 20}),
    ]
    warmed = 0
    failures: list[dict[str, str]] = []
    for path, query in targets:
        try:
            await gateway.request("GET", path, query_params=query)
            warmed += 1
        except Exception as exc:  # noqa: BLE001
            failures.append({"path": path, "error": str(exc)})
    return {
        "total": len(targets),
        "warmed": warmed,
        "failed": len(failures),
        "failures": failures,
        "ok": warmed > 0 and not failures,
    }
