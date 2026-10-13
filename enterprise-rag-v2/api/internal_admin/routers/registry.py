from fastapi import FastAPI

from api.internal_admin.routers.tenants import router as internal_admin_tenants_router
from api.internal_admin.routers.ops import router as internal_admin_ops_router
from api.internal_admin.routers.audit import router as internal_admin_audit_router
from api.internal_admin.routers.documents import router as internal_admin_documents_router
from api.internal_admin.routers.quotas import router as internal_admin_quotas_router
from api.internal_admin.routers.cache import router as internal_admin_cache_router


def register_internal_admin_routes(app: FastAPI) -> None:
    """集中注册 Internal Admin 路由。"""
    app.include_router(internal_admin_tenants_router, prefix="/internal/admin", tags=["Internal Admin"])
    app.include_router(internal_admin_ops_router, prefix="/internal/admin", tags=["Internal Admin"])
    app.include_router(internal_admin_audit_router, prefix="/internal/admin", tags=["Internal Admin"])
    app.include_router(internal_admin_documents_router, prefix="/internal/admin", tags=["Internal Admin"])
    app.include_router(internal_admin_quotas_router, prefix="/internal/admin", tags=["Internal Admin"])
    app.include_router(internal_admin_cache_router, prefix="/internal/admin", tags=["Internal Admin"])
