"""
Celery worker 进程内唯一 asyncio 事件循环。

chat_tasks / document_tasks / ops_tasks 必须与同一事件循环配合使用全局
`AsyncSessionLocal` 所用的 engine；若各模块各自 `new_event_loop()`，
asyncpg 连接池会在不同 loop 上混用，触发
「Future ... attached to a different loop」。
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from infrastructure.database.session import engine
from infrastructure.logging.logger import get_logger

logger = get_logger("infrastructure.queue.celery_asyncio")

T = TypeVar("T")

_WORKER_LOOP: asyncio.AbstractEventLoop | None = None


def _dispose_engine_pool_sync() -> None:
    """在替换已关闭的事件循环前同步释放连接池，避免连接仍绑在旧 loop 上。"""
    try:
        engine.sync_engine.dispose()
    except Exception as e:
        logger.warning(
            "替换 Celery 事件循环前 sync_engine.dispose() 失败: %s",
            e,
            exc_info=True,
        )


def get_worker_event_loop() -> asyncio.AbstractEventLoop:
    """
    返回当前 Celery worker 进程内唯一的事件循环。
    所有使用 AsyncSessionLocal 的后台任务应共用此循环。
    """
    global _WORKER_LOOP
    if _WORKER_LOOP is None:
        _WORKER_LOOP = asyncio.new_event_loop()
        logger.info(
            "celery_asyncio: 初始化 worker 事件循环 loop_id=%s closed=%s",
            id(_WORKER_LOOP),
            _WORKER_LOOP.is_closed(),
        )
        return _WORKER_LOOP

    if _WORKER_LOOP.is_closed():
        old_id = id(_WORKER_LOOP)
        logger.warning(
            "celery_asyncio: 原事件循环已关闭 old_loop_id=%s，dispose 连接池并重建",
            old_id,
        )
        _dispose_engine_pool_sync()
        _WORKER_LOOP = asyncio.new_event_loop()
        logger.info(
            "celery_asyncio: 已重建 worker 事件循环 new_loop_id=%s",
            id(_WORKER_LOOP),
        )
    return _WORKER_LOOP


def run_coroutine(coro: Coroutine[Any, Any, T]) -> T:
    """在 worker 唯一事件循环上运行协程（Celery 同步任务入口使用）。"""
    loop = get_worker_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
