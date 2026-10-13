from api.internal_admin.routers.tenants import router as internal_admin_tenants_router
from api.internal_admin.routers.ops import router as internal_admin_ops_router
from api.internal_admin.routers.audit import router as internal_admin_audit_router
from api.internal_admin.routers.documents import router as internal_admin_documents_router
from api.internal_admin.routers.quotas import router as internal_admin_quotas_router
from api.internal_admin.routers.registry import register_internal_admin_routes

__all__ = [
    "internal_admin_tenants_router",
    "internal_admin_ops_router",
    "internal_admin_audit_router",
    "internal_admin_documents_router",
    "internal_admin_quotas_router",
    "register_internal_admin_routes",
]

