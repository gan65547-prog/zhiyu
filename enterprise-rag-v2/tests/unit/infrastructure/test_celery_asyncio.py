"""Celery worker 内唯一事件循环的回归测试（避免多模块各自 new_event_loop 导致 asyncpg 跨 loop）。"""

from infrastructure.queue import document_tasks
from infrastructure.queue.celery_asyncio import get_worker_event_loop, run_coroutine


async def _sample_coro() -> str:
    return "ok"


def test_get_worker_event_loop_is_singleton() -> None:
    a = get_worker_event_loop()
    b = get_worker_event_loop()
    assert a is b
    assert not a.is_closed()


def test_document_tasks_uses_same_loop_helper() -> None:
    assert document_tasks.get_worker_event_loop is get_worker_event_loop


def test_run_coroutine() -> None:
    assert run_coroutine(_sample_coro()) == "ok"
