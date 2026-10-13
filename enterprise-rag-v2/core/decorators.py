"""
通用装饰器
"""

import functools
from typing import Awaitable, Callable, ParamSpec, TypeVar

from infrastructure.logging.logger import get_logger

P = ParamSpec("P")
T = TypeVar("T")


def log_exceptions(logger_name: str) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """为异步函数补充统一异常日志，避免重复的 catch-then-raise 模板代码。"""

    logger = get_logger(logger_name)

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.exception("%s failed", func.__name__)
                raise

        return wrapper

    return decorator
