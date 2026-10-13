import functools
from typing import Callable, Optional

from fastapi import HTTPException, Request
from ..models import QuotaExceededError
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def check_quota(dimension: str):
    """
    资源上限检查装饰器

    使用方式：
    @router.post("/documents")
    @check_quota("documents")
    async def create_document(...):
        pass

    功能：
    1. 自动提取tenant_id（从request.state）
    2. 检查指定维度是否达到部署者设置的上限
    3. 超限时直接抛出QuotaExceededError → 统一异常处理器返回资源上限提示
    4. 成功后自动增加使用量

    集成点：
    - 文档上传API: @check_quota("documents") + @check_quota("storage_mb")
    - 对话API: @check_quota("api_calls_monthly") 或 @check_quota("chat_messages_monthly")
    - 检索API: @check_quota("api_calls_monthly")
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从args中提取request对象（FastAPI依赖注入）
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # 尝试从kwargs获取
                request = kwargs.get('request')

            if not request:
                raise RuntimeError("check_quota装饰器需要Request对象")

            tenant_id = getattr(request.state, 'tenant_id', None)
            if not tenant_id:
                raise RuntimeError("无法获取tenant_id，请确保认证中间件已设置")

            # 获取QuotaService实例
            quota_svc = getattr(request.app.state, 'quota_service', None)
            if not quota_svc:
                logger.error("QuotaService未初始化，跳过配额检查")
                return await func(*args, **kwargs)

            try:
                # 检查配额
                is_ok, current, limit_val, pct = await quota_svc.check_quota(tenant_id, dimension)

                if not is_ok:
                    logger.info(
                        f"配额超限: tenant={tenant_id}, {dimension}={current}/{limit_val}",
                        extra={"tenant_id": tenant_id, "dimension": dimension,
                               "current": current, "limit": limit_val}
                    )
                    raise QuotaExceededError(dimension, current, limit_val)

                # 执行原函数
                result = await func(*args, **kwargs)

                # 成功后增加使用量
                try:
                    await quota_svc.increment_usage(tenant_id, dimension, 1)
                except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                    logger.warning(f"增加使用量失败: {e}", exc_info=True)

                return result

            except QuotaExceededError:
                raise  # 直接抛出，由全局异常处理器处理

        return wrapper
    return decorator
