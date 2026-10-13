"""
集成路由模块
"""

from apps.integration.routers.health import router as health_router
from apps.integration.routers.chat import router as chat_router
from apps.integration.routers.bind import router as bind_router

__all__ = ["health_router", "chat_router", "bind_router"]
