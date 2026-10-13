"""
Celery 应用实例

用于异步文档处理等后台任务。
"""

import os
from celery import Celery

from core.config import get_settings
from infrastructure.logging.logger import LoggerFactory, JSONLogFormatter, FileLogHandler, ConsoleLogHandler

settings = get_settings()


def init_worker_logging() -> None:
    """初始化 Celery worker 的结构化日志输出。"""
    handlers = [ConsoleLogHandler(JSONLogFormatter())]
    if settings.log.file_path:
        log_path = settings.log.file_path
        if not os.path.isabs(log_path):
            # 与 main.py 保持一致：相对路径相对于项目根。
            log_path = os.path.join(os.getcwd(), log_path)
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(FileLogHandler(log_path, JSONLogFormatter()))

    LoggerFactory._default_handlers = handlers
    LoggerFactory.refresh_handlers()


init_worker_logging()

celery_app = Celery(
    "enterprise_rag",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

celery_app.conf.update(
    task_serializer=settings.celery.task_serializer,
    result_serializer=settings.celery.result_serializer,
    accept_content=["json"],
    imports=(
        "infrastructure.queue.document_tasks",
        "infrastructure.queue.asset_tasks",
        "infrastructure.queue.research_tasks",
        "infrastructure.queue.knowledge_tasks",
        "infrastructure.queue.content_tasks",
        "infrastructure.queue.chat_tasks",
        "infrastructure.queue.ops_tasks",
    ),
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    worker_concurrency=settings.celery.worker_concurrency,
    timezone="Asia/Shanghai",
    enable_utc=False,
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=1048576,
    worker_disable_rate_limits=False,
    task_soft_time_limit=1800,
    task_time_limit=3600,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=10,
    beat_schedule={
        "agent-dispatch-due-schedules": {
            "task": "agent.dispatch_due_schedules",
            "schedule": 60.0,
        },
        "content-dispatch-due-schedules": {
            "task": "content.dispatch_due_schedules",
            "schedule": 60.0,
        },
    },
)
