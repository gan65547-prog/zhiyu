"""
quota_overrides 表行数类指标（Prometheus Gauge），启动时刷新一次。
"""

from __future__ import annotations

from typing import Any

from prometheus_client import Gauge

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

QUOTA_OVERRIDE_ACTIVE_TOTAL = Gauge(
    "quota_override_active_total",
    "当前仍生效的配额覆盖规则行数（expires_at 为空或未来）",
)

QUOTA_OVERRIDE_EXPIRED_TOTAL = Gauge(
    "quota_override_expired_total",
    "已过期但仍保留在表中的配额覆盖行数",
)


async def refresh_quota_override_gauges(db: Any) -> None:
    """从数据库统计并写入 Gauge；失败时仅打日志。"""
    try:
        active_row = await db.fetch_one(
            """
            SELECT COUNT(*) AS c
            FROM quota_overrides
            WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP
            """
        )
        expired_row = await db.fetch_one(
            """
            SELECT COUNT(*) AS c
            FROM quota_overrides
            WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP
            """
        )
        active = int(dict(active_row).get("c", 0)) if active_row else 0
        expired = int(dict(expired_row).get("c", 0)) if expired_row else 0
        QUOTA_OVERRIDE_ACTIVE_TOTAL.set(active)
        QUOTA_OVERRIDE_EXPIRED_TOTAL.set(expired)
    except Exception as e:
        logger.warning("refresh_quota_override_gauges failed: %s", e, exc_info=True)
