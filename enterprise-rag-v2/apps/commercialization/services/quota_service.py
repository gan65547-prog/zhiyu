from typing import Dict, Any, Optional, List

from ..config import settings
from ..config_quota import get_quota_limit, build_quota_key
from ..models import QuotaExceededError
from infrastructure.monitoring.metrics import get_metrics_collector
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)
metrics = get_metrics_collector()


class QuotaService:
    """配额管理服务"""

    # 配额维度定义
    DIMENSIONS = [
        "users", "documents", "storage_mb", "api_calls_monthly", "chat_messages_monthly", "workspaces",
        "research_runs_monthly", "research_sources_monthly", "research_output_tokens_monthly",
    ]

    def __init__(self, db, redis):
        self.db = db
        self.redis = redis

    @staticmethod
    def _override_cache_key(tenant_id: str, dimension: str) -> str:
        return f"quota_override:{tenant_id}:{dimension}"

    async def _get_override_limit(self, tenant_id: str, dimension: str) -> Optional[int]:
        """读取人工配额覆盖值，优先缓存，失效后回源数据库。"""
        cache_key = self._override_cache_key(tenant_id, dimension)
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                import json
                payload = json.loads(cached)
                expires_at_raw = payload.get("expires_at")
                if expires_at_raw:
                    from datetime import datetime, timezone
                    expires_at = datetime.fromisoformat(expires_at_raw)
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at <= datetime.now(timezone.utc):
                        await self.redis.delete(cache_key)
                        return None
                value = payload.get("override_value")
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        except (RuntimeError, ValueError, TypeError, AttributeError):
            pass

        try:
            row = await self.db.fetch_one(
                """
                SELECT override_value, expires_at
                FROM quota_overrides
                WHERE tenant_id = :tenant_id
                  AND dimension = :dimension
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                LIMIT 1
                """,
                {"tenant_id": tenant_id, "dimension": dimension},
            )
        except Exception as exc:
            # 配额覆盖是增强能力，数据库驱动的时间类型异常不能阻塞主业务。
            logger.warning("读取配额覆盖失败，使用默认资源上限: tenant=%s dimension=%s error=%s", tenant_id, dimension, exc)
            return None
        if not row:
            return None

        row_data = dict(row)
        override_value = int(row_data["override_value"])
        try:
            import json
            expires_at = row_data.get("expires_at")
            await self.redis.setex(
                cache_key,
                300,
                json.dumps(
                    {
                        "tenant_id": tenant_id,
                        "dimension": dimension,
                        "override_value": override_value,
                        "expires_at": expires_at.isoformat() if hasattr(expires_at, "isoformat") else None,
                    },
                    ensure_ascii=False,
                ),
            )
        except (RuntimeError, ValueError, TypeError, AttributeError):
            pass
        return override_value

    async def _get_realtime_usage(self, tenant_id: str) -> Dict[str, int]:
        """从数据库实时统计组织级资源使用量（避免仅靠Redis导致展示失真）"""
        users_row = await self.db.fetch_one(
            "SELECT COUNT(*) AS c FROM users WHERE tenant_id = :tenant_id",
            {"tenant_id": tenant_id}
        )
        workspaces_row = await self.db.fetch_one(
            "SELECT COUNT(*) AS c FROM workspaces WHERE tenant_id = :tenant_id",
            {"tenant_id": tenant_id}
        )
        documents_row = await self.db.fetch_one(
            """
            SELECT COUNT(*) AS c
            FROM documents d
            JOIN datasets ds ON d.dataset_id = ds.id
            JOIN workspaces w ON ds.workspace_id = w.id
            WHERE w.tenant_id = :tenant_id
            """,
            {"tenant_id": tenant_id}
        )
        storage_row = await self.db.fetch_one(
            """
            SELECT COALESCE(SUM(d.file_size), 0) AS bytes_sum
            FROM documents d
            JOIN datasets ds ON d.dataset_id = ds.id
            JOIN workspaces w ON ds.workspace_id = w.id
            WHERE w.tenant_id = :tenant_id
            """,
            {"tenant_id": tenant_id}
        )

        bytes_sum = int(storage_row["bytes_sum"] or 0)
        storage_mb = (bytes_sum + 1024 * 1024 - 1) // (1024 * 1024) if bytes_sum > 0 else 0

        return {
            "users": int(users_row["c"] or 0),
            "workspaces": int(workspaces_row["c"] or 0),
            "documents": int(documents_row["c"] or 0),
            "storage_mb": int(storage_mb),
        }

    async def check_quota(self, tenant_id: str, dimension: str, amount: int = 0) -> tuple:
        """
        检查配额是否超限

        Returns:
            (is_ok: bool, current: int, limit: int, percentage: float)
            - is_ok: True表示未超限，False表示已超限
            - current: 当前使用量
            - limit: 配额上限
            - percentage: 使用百分比 (0-100)
        """
        # 自托管开源版默认不按套餐限制；维护者可以通过 quota_overrides
        # 为资源有限的部署设置明确上限。
        plan = "unlimited"
        limits = dict(get_quota_limit())

        max_allowed = limits.get(dimension, 0)
        override_limit = await self._get_override_limit(tenant_id, dimension)
        if override_limit is not None:
            max_allowed = override_limit

        # users/documents/workspaces/storage_mb 用实时数据库值，调用/消息类用Redis计数
        if dimension in {"users", "documents", "workspaces", "storage_mb"}:
            realtime = await self._get_realtime_usage(tenant_id)
            current = int(realtime.get(dimension, 0))
        else:
            quota_key = build_quota_key(tenant_id)
            try:
                current_str = await self.redis.hget(quota_key, dimension)
                current = int(current_str) if current_str else 0
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"读取配额计数失败，按0处理: tenant={tenant_id}, dim={dimension}, error={e}")
                current = 0

        # 计算使用百分比
        percentage = (current / max_allowed * 100) if max_allowed > 0 else 0

        # 检查是否超限（-1表示无限制）
        projected = current + max(0, int(amount))
        at_or_over_limit = current >= max_allowed if amount == 0 else projected > max_allowed
        if max_allowed != -1 and at_or_over_limit:
            logger.warning(
                f"⚠️ 配额超限: tenant={tenant_id}, "
                f"dimension={dimension}, current={current}/{max_allowed}"
            )
            
            # 记录配额超限指标
            metrics.increment("quota.exceeded", 1.0, {
                "dimension": dimension,
                "plan": plan
            })
            
            raise QuotaExceededError(dimension, current, max_allowed)

        return True, current, max_allowed, round(percentage, 1)

    async def assert_can_add_document(self, tenant_id: str, file_size_bytes: int) -> None:
        """
        上传前校验文档数和管理员配置的投影存储上限。
        """
        await self.check_quota(tenant_id, "documents")

        max_mb = await self._get_override_limit(tenant_id, "storage_mb")
        if max_mb is None:
            max_mb = -1
        if max_mb == -1:
            return

        storage_row = await self.db.fetch_one(
            """
            SELECT COALESCE(SUM(d.file_size), 0) AS bytes_sum
            FROM documents d
            JOIN datasets ds ON d.dataset_id = ds.id
            JOIN workspaces w ON ds.workspace_id = w.id
            WHERE w.tenant_id = :tenant_id
            """,
            {"tenant_id": tenant_id},
        )
        bytes_sum = int(storage_row["bytes_sum"] or 0)
        new_total = bytes_sum + int(file_size_bytes)
        limit_bytes = max_mb * 1024 * 1024
        if new_total > limit_bytes:
            used_mb = (bytes_sum + 1024 * 1024 - 1) // (1024 * 1024) if bytes_sum > 0 else 0
            add_mb = (int(file_size_bytes) + 1024 * 1024 - 1) // (1024 * 1024) if file_size_bytes > 0 else 0
            projected = used_mb + add_mb
            raise QuotaExceededError("storage_mb", projected, max_mb)

    async def increment_usage(self, tenant_id: str, dimension: str, amount: int = 1):
        """
        增加配额使用量（原子操作）

        使用Redis HINCRBY保证并发安全
        """
        quota_key = build_quota_key(tenant_id)
        new_value = await self.redis.hincrby(quota_key, dimension, amount)

        logger.debug(
            f"📊 配额增加: tenant={tenant_id}, "
            f"dimension={dimension}, +{amount} = {new_value}"
        )

        return new_value

    async def decrement_usage(self, tenant_id: str, dimension: str, amount: int = 1):
        """减少配额使用量"""
        quota_key = build_quota_key(tenant_id)
        new_value = await self.redis.hincrby(quota_key, dimension, -amount)

        # 防止负数
        if new_value < 0:
            await self.redis.hset(quota_key, dimension, 0)
            new_value = 0

        return new_value

    async def get_usage_info(self, tenant_id: str) -> Dict[str, Any]:
        """
        获取完整的配额使用信息

        Returns:
            {
                usage: {dimension: current_value},
                limits: {dimension: max_limit},
                percentages: {dimension: usage_percent},
                warnings: [接近上限的维度列表]
            }
        """
        # 默认无限制；quota_overrides 由自托管部署者在运维控制面管理。
        plan = "unlimited"
        limits = dict(get_quota_limit())
        for dim in self.DIMENSIONS:
            override_limit = await self._get_override_limit(tenant_id, dim)
            if override_limit is not None:
                limits[dim] = override_limit

        # 获取Redis中的计数型维度
        quota_key = build_quota_key(tenant_id)
        try:
            usage_data = await self.redis.hgetall(quota_key) or {}
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"读取配额缓存失败，使用默认值: tenant={tenant_id}, error={e}")
            usage_data = {}

        realtime_usage = await self._get_realtime_usage(tenant_id)

        usage = {}
        percentages = {}
        warnings = []

        for dim in self.DIMENSIONS:
            if dim in {"users", "documents", "workspaces", "storage_mb"}:
                current = int(realtime_usage.get(dim, 0))
            else:
                current = int(usage_data.get(dim, 0))
            limit_val = limits.get(dim, 0)

            usage[dim] = current

            # 计算百分比
            if limit_val > 0:
                pct = round(current / limit_val * 100, 1)
                percentages[dim] = pct

                # 接近上限时警告（>80%）
                if pct >= 80:
                    warnings.append({
                        "dimension": dim,
                        "current": current,
                        "limit": limit_val,
                        "percentage": pct,
                    })
            else:
                percentages[dim] = 0.0

        return {
            "tenant_id": tenant_id,
            "plan": plan,
            "usage": usage,
            "limits": limits,
            "percentages": percentages,
            "warnings": warnings,
        }

    async def init_free_tier(self, tenant_id: str, user_email: str = None) -> Dict[str, Any]:
        """
        初始化租户资源统计

        在以下场景调用：
        1. 用户首次注册成功后
        2. 新租户创建时

        Args:
            tenant_id: 租户ID
            user_email: 用户邮箱（用于日志）

        Returns:
            {
                "success": True,
                "tenant_id": "...",
                "plan": "free",
                "limits": {...},
                "message": "租户资源统计已初始化"
            }
        """
        plan = "unlimited"
        limits = get_quota_limit()
        quota_key = build_quota_key(tenant_id)

        # 使用Redis Pipeline原子化初始化所有维度
        pipe = await self.redis.pipeline()

        # 初始化所有维度为0
        for dim in self.DIMENSIONS:
            pipe.hset(quota_key, dim, 0)

        # 设置TTL为7天（防止僵尸数据，正常情况下会被活跃用户刷新）
        pipe.expire(quota_key, 604800)  # 7天

        results = await pipe.execute()

        logger.info(
            f"租户资源统计初始化成功: tenant={tenant_id}, "
            f"email={user_email}, plan=UNLIMITED, "
            f""
            f""
            f""
        )

        return {
            "success": True,
            "tenant_id": tenant_id,
            "plan": plan,
            "limits": limits,
            "message": "资源统计已初始化 - 欢迎使用知域！",
            "next_steps": [
                "可以开始上传文档并使用检索功能",
                "可由部署者在运维控制面配置资源上限"
            ]
        }

    async def reset_monthly_quotas(self, tenant_id: str):
        """
        重置每月配额（定时任务）

        每月1日执行，重置 api_calls_monthly 和 chat_messages_monthly
        """
        monthly_dims = [
            "api_calls_monthly", "chat_messages_monthly", "research_runs_monthly",
            "research_sources_monthly", "research_output_tokens_monthly",
        ]
        quota_key = build_quota_key(tenant_id)

        pipe = await self.redis.pipeline()
        for dim in monthly_dims:
            pipe.hset(quota_key, dim, 0)
        await pipe.execute()

        logger.debug(f"♻️ 每月配额重置: tenant={tenant_id}")

    async def check_and_increment(self, tenant_id: str, dimension: str, amount: int = 1):
        """
        检查配额并自动增加（原子操作）

        用于API层快速检查+计数
        """
        # 先检查
        if amount < 0:
            raise ValueError("配额增加量不能为负数")
        is_ok, current, limit_val, pct = await self.check_quota(tenant_id, dimension, amount)

        if not is_ok:
            raise QuotaExceededError(dimension, current, limit_val)

        # 再增加
        new_value = await self.increment_usage(tenant_id, dimension, amount)

        return True, new_value, limit_val

    async def get_quota_for_dimension(self, tenant_id: str, dimension: str) -> Dict[str, Any]:
        """查询单个维度的配额状态"""
        try:
            is_ok, current, limit_val, pct = await self.check_quota(tenant_id, dimension)
            return {
                "dimension": dimension,
                "current": current,
                "limit": limit_val,
                "percentage": pct,
                "remaining": max(0, limit_val - current),
                "is_ok": is_ok,
            }
        except QuotaExceededError as e:
            return {
                "dimension": dimension,
                "current": e.current,
                "limit": e.limit,
                "percentage": 100.0,
                "remaining": 0,
                "is_ok": False,
                "error": str(e),
            }
