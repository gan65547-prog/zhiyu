"""
API Routers
"""

from api.routers.auth import router as auth_router
from api.routers.tenants import router as tenants_router
from api.routers.workspaces import router as workspaces_router
from api.routers.datasets import router as datasets_router
from api.routers.documents import router as documents_router
from api.routers.chat import router as chat_router
from api.routers.oauth import router as oauth_router
from api.routers.backups import router as backup_router
from api.routers.webhooks import router as webhooks_router
from api.routers.users import router as users_router
from api.routers.learning import router as learning_router
from api.routers.errata import errata_router
from api.routers.assets import router as assets_router
from api.routers.knowledge import router as knowledge_router
from api.routers.research import router as research_router
from api.routers.agents import router as agents_router
from api.routers.content import router as content_router
from api.routers.workbench import router as workbench_router
from api.routers.data_center import router as data_center_router
from api.routers.knowledge_relations import router as knowledge_relations_router

__all__ = [
    "auth_router",
    "tenants_router",
    "workspaces_router",
    "datasets_router",
    "documents_router",
    "chat_router",
    "oauth_router",
    "backup_router",
    "webhooks_router",
    "users_router",
    "learning_router",
    "errata_router",
    "assets_router",
    "knowledge_router",
    "research_router",
    "agents_router",
    "content_router",
    "workbench_router",
    "data_center_router",
    "knowledge_relations_router",
]
