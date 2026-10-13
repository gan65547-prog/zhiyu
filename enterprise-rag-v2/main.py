"""
Enterprise RAG System v2 - 应用入口

FastAPI应用主入口文件
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import Annotated
import os
import logging as _std_logging

from core.config import get_settings
from core.container import Container
from infrastructure.cache import close_cache
from infrastructure.monitoring import get_health_checker, get_metrics_collector
from infrastructure.logging.logger import (
    LoggerFactory,
    JSONLogFormatter,
    FileLogHandler,
    ConsoleLogHandler,
    StandardLibJSONHandler,
    get_logger,
    LogLevel,
)


settings = get_settings()

def init_logging():
    """初始化日志系统"""
    handlers = []
    
    # 控制台日志处理器
    console_handler = ConsoleLogHandler(JSONLogFormatter())
    handlers.append(console_handler)
    
    # 文件日志处理器（如果配置了）
    if settings.log.file_path:
        # 使用绝对路径
        log_path = settings.log.file_path
        if not os.path.isabs(log_path):
            log_path = os.path.join(os.path.dirname(__file__), log_path)
        
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = FileLogHandler(
            file_path=log_path,
            formatter=JSONLogFormatter(),
            max_bytes=settings.log.max_file_size,
            backup_count=settings.log.backup_count,
        )
        handlers.append(file_handler)
    
    # 设置全局日志处理器
    _level_map = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
        "CRITICAL": LogLevel.CRITICAL,
    }
    LoggerFactory.set_global_level(
        _level_map.get(settings.log.level.upper(), LogLevel.INFO)
    )
    LoggerFactory._default_handlers = handlers
    
    # 刷新所有已创建 logger 的处理器
    LoggerFactory.refresh_handlers()

    # 兼容标准库 logging，统一写入 JSON 文件
    root = _std_logging.getLogger()
    root.setLevel(getattr(_std_logging, settings.log.level.upper(), _std_logging.INFO))
    root.handlers.clear()
    if settings.log.file_path:
        root.addHandler(
            StandardLibJSONHandler(
                file_path=log_path,
                max_bytes=settings.log.max_file_size,
                backup_count=settings.log.backup_count,
            )
        )

init_logging()
logger = get_logger("main")

# 现在再导入 API 相关模块（确保在 init_logging 之后）
from api.routers import (
    auth_router,
    tenants_router,
    workspaces_router,
    datasets_router,
    documents_router,
    chat_router,
    oauth_router,
    backup_router,
    webhooks_router,
    users_router,
    learning_router,
    errata_router,
    assets_router,
    knowledge_router,
    research_router,
    agents_router,
    content_router,
    workbench_router,
    data_center_router,
    knowledge_relations_router,
)
from api.internal_admin.routers.registry import register_internal_admin_routes
from api.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    TenantContextMiddleware,
    RegistrationRateLimitMiddleware,
    CSRFMiddleware,
    MonthlyApiQuotaMiddleware,
)
from api.middleware.internal_admin_metrics import InternalAdminMetricsMiddleware
from api.deps import require_metrics_access

# 自托管资源配额
from apps.commercialization.routers import quotas_router
from apps.commercialization.services import QuotaService
from apps.commercialization.models import QuotaExceededError

# 集成模块导入 (OpenClaw混合架构)
from apps.integration.routers import (
    health_router as integration_health_router,
    chat_router as integration_chat_router,
    bind_router as integration_bind_router,
)
from apps.integration.middleware.gateway_auth import GatewayAuthMiddleware
from fastapi import Depends, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings.validate_production_secrets()

    container = Container()
    await container.init_services()

    # 初始化用量统计与资源限制服务（默认无限；管理员可显式设置资源上限）
    from infrastructure.cache import get_cache
    from databases import Database
    
    # 创建databases库实例
    db_url = settings.database.url
    db = Database(db_url)
    await db.connect()
    
    redis_client = await get_cache()
    
    # 初始化配额服务
    app.state.quota_service = QuotaService(
        db=db,
        redis=redis_client
    )
    
    # 存储db实例，用于关闭连接
    app.state.db = db

    try:
        from infrastructure.monitoring.quota_override_metrics import (
            refresh_quota_override_gauges,
        )

        await refresh_quota_override_gauges(db)
    except Exception as e:
        logger.warning("quota_override gauges not refreshed at startup: %s", e)

    logger.info(
        f"{settings.app_name} v{settings.app_version} started",
        __module__="main"
    )

    yield

    # ========== 优雅关闭阶段 ==========
    logger.info("Shutdown phase 1/6: stopping Celery worker (best-effort)...")
    try:
        from infrastructure.queue.celery_app import celery_app
        # 通知 Celery 停止接受新任务（不强制等待运行中的任务）
        celery_app.control.broadcast('shutdown')
        logger.info("  -> Celery shutdown signal sent")
    except Exception as e:
        logger.warning("  -> Celery shutdown notification failed: %s", e)

    logger.info("Shutdown phase 2/6: draining HTTP connections...")
    # Uvicorn 在 lifespan shutdown 前已停止 accept 新连接并等待进行中请求完成。
    # 此处仅记录日志，实际 draining 由 uvicorn/guinicorn 主循环完成。
    import asyncio
    await asyncio.sleep(0.1)  # 给 event loop 一个 tick 刷新挂起的回调

    logger.info("Shutdown phase 3/6: closing database connections...")
    if hasattr(app.state, 'db'):
        try:
            await app.state.db.disconnect()
            logger.info("  -> Database connection closed")
        except Exception as e:
            logger.warning("  -> Database disconnect failed: %s", e)
    try:
        from infrastructure.database.session import engine as _db_engine
        await _db_engine.dispose()
        logger.info("  -> SQLAlchemy engine disposed")
    except Exception as e:
        logger.warning("  -> Engine dispose failed: %s", e)

    logger.info("Shutdown phase 4/6: closing cache (Redis) connections...")
    try:
        await close_cache()
        logger.info("  -> Cache connections closed")
    except Exception as e:
        logger.warning("  -> Cache close failed: %s", e)

    logger.info("Shutdown phase 6/6: releasing Embedding model memory...")
    try:
        from core.rag.embedding import SentenceTransformerEmbedding
        SentenceTransformerEmbedding.close()
        logger.info("  -> Embedding model memory released")
    except Exception as e:
        logger.warning("  -> Embedding model cleanup failed: %s", e)

    logger.info("Application shutdown complete", __module__="main")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="企业级RAG系统 - 支持多租户、高并发、可扩展",
        # 生产环境中始终启用 API 文档，通过 Nginx 内网白名单 + FastAPI 依赖双重保护
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan
    )

    # 最先注册、最靠近路由：按月 API 调用配额（需 JWT 中 tenant_id）
    app.add_middleware(MonthlyApiQuotaMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.add_middleware(SecurityHeadersMiddleware)
    # JSON body 安全校验中间件默认关闭（历史上曾触发 POST 卡死/worker timeout）。
    # 仅在灰度或压测验证通过后，通过环境变量显式开启。
    if os.getenv("ENABLE_JSON_BODY_SECURITY", "false").lower() in {"1", "true", "yes", "on"}:
        from api.middleware import JsonBodySecurityMiddleware
        app.add_middleware(JsonBodySecurityMiddleware)
    app.add_middleware(RegistrationRateLimitMiddleware)

    if settings.security.csrf_enabled:
        app.add_middleware(CSRFMiddleware, enabled=True)

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantContextMiddleware)
    
    # 限流中间件放在最后，确保CORS头在限流错误时也能正确设置
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.security.rate_limit_per_minute
    )

    # 集成模块网关认证中间件 (验证OpenClaw请求)
    app.add_middleware(GatewayAuthMiddleware)
    # 最后注册、最靠近客户端：统计 /internal/admin 全链路耗时
    app.add_middleware(InternalAdminMetricsMiddleware)

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["租户"])
    app.include_router(workspaces_router, prefix="/api/v1/workspaces", tags=["工作空间"])
    app.include_router(datasets_router, prefix="/api/v1/datasets", tags=["数据集"])
    app.include_router(documents_router, prefix="/api/v1/documents", tags=["文档"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["对话"])
    app.include_router(oauth_router, prefix="/api/v1/oauth", tags=["第三方登录"])
    app.include_router(backup_router, prefix="/api/v1/backups", tags=["备份恢复"])
    app.include_router(webhooks_router, prefix="/api/v1/webhooks", tags=["Webhook"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["用户"])
    app.include_router(learning_router, prefix="/api/v1/learning", tags=["学习诊断"])
    app.include_router(errata_router, tags=["勘误"])
    app.include_router(assets_router, prefix="/api/v1/assets", tags=["素材"])
    app.include_router(knowledge_router, prefix="/api/v1/knowledge/items", tags=["知识中心"])
    app.include_router(research_router, prefix="/api/v1/research", tags=["研究洞察"])
    app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agent Runtime"])
    app.include_router(content_router, prefix="/api/v1/content", tags=["Content Center"])
    app.include_router(workbench_router, prefix="/api/v1/workbench", tags=["AI 工作台"])
    app.include_router(data_center_router, prefix="/api/v1/data-center", tags=["数据中心"])
    app.include_router(knowledge_relations_router, prefix="/api/v1/knowledge/relations", tags=["知识关系网络"])
    register_internal_admin_routes(app)

    # 自托管资源用量查看与治理
    app.include_router(quotas_router, tags=["配额"])

    # 集成路由 (OpenClaw混合架构 - 消息网关接入)
    app.include_router(
        integration_health_router,
        prefix="/api/v1/integration",
        tags=["Integration"]
    )
    app.include_router(
        integration_chat_router,
        prefix="/api/v1/integration",
        tags=["Integration"]
    )
    app.include_router(
        integration_bind_router,
        prefix="/api/v1/integration",
        tags=["Integration"]
    )

    # 全局异常处理器 - 配额超限（含升级提示）
    @app.exception_handler(QuotaExceededError)
    async def quota_exceeded_handler(request: Request, exc: QuotaExceededError):
        """处理配额超限错误，返回升级提示"""
        logger.warning(
            f"配额超限: {exc.dimension}={exc.current}/{exc.limit}, 用户可能需要升级",
            extra={
                "dimension": exc.dimension,
                "current": exc.current,
                "limit": exc.limit,
                "path": request.url.path
            }
        )
        return JSONResponse(
            status_code=403,
            content=exc.to_response_dict()
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """保留认证、CSRF 和权限异常的真实 HTTP 状态码。"""
        detail = exc.detail if isinstance(exc.detail, (dict, list, str, int, float, bool)) else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers or {})

    # 全局异常处理器 - 未捕获的 500 错误
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """兜底异常处理器，确保未捕获异常返回统一 JSON 格式"""
        import uuid
        error_id = str(uuid.uuid4())
        logger.error(
            f"Unhandled exception [{error_id}]: {exc}",
            extra={"path": request.url.path, "method": request.method},
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_id": error_id}
        )

    @app.get("/health", tags=["系统"])
    async def health_check():
        """健康检查"""
        health_checker = get_health_checker()
        result = await health_checker.check_all()
        return result

    @app.get("/health/live", tags=["系统"])
    async def liveness_check():
        """存活检查"""
        return {"status": "alive"}

    @app.get("/health/ready", tags=["系统"])
    async def readiness_check():
        """就绪检查"""
        health_checker = get_health_checker()
        result = await health_checker.check_all()

        if result["status"] == "unhealthy":
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result
            )

        return result

    @app.get("/metrics", tags=["系统"])
    async def get_metrics(
        _: Annotated[None, Depends(require_metrics_access)]
    ):
        """获取系统指标"""
        collector = get_metrics_collector()
        return collector.get_all_metrics()

    @app.get("/metrics/prometheus", tags=["系统"])
    async def get_prometheus_metrics(
        _: Annotated[None, Depends(require_metrics_access)]
    ):
        """Prometheus 文本格式（含 /internal/admin 与集成模块等注册指标）。"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # 生产镜像内若存在 frontend/dist，则由同一端口提供 Vue SPA + API（用户访问 http://host:8000/）
    _frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
    if _frontend_dist.is_dir():
        index_html = _frontend_dist / "index.html"

        # 为前端SPA创建路由处理
        # 注意：这些路由必须在API路由之后注册
        # 但由于FastAPI的路由匹配机制，通配符路由会匹配所有路径
        # 因此我们需要确保API路由能够优先匹配

        # 处理根路径
        @app.get("/", include_in_schema=False)
        async def spa_index():
            return FileResponse(index_html)

        # 处理静态文件
        @app.get("/assets/{path:path}", include_in_schema=False)
        async def spa_static_assets(path: str):
            candidate = _frontend_dist / "assets" / path
            if candidate.is_file():
                return FileResponse(candidate)
            raise HTTPException(status_code=404, detail="Not Found")

        # 处理favicon
        @app.get("/favicon.svg", include_in_schema=False)
        async def spa_favicon():
            candidate = _frontend_dist / "favicon.svg"
            if candidate.is_file():
                return FileResponse(candidate)
            raise HTTPException(status_code=404, detail="Not Found")

        # 处理前端路由，但排除API路径
        # 使用多个具体的路由模式，避免与API路由冲突
        @app.get("/login", include_in_schema=False)
        @app.get("/register", include_in_schema=False)
        @app.get("/chat", include_in_schema=False)
        @app.get("/chat/{path:path}", include_in_schema=False)
        @app.get("/workbench", include_in_schema=False)
        @app.get("/workbench/{path:path}", include_in_schema=False)
        @app.get("/tasks", include_in_schema=False)
        @app.get("/tasks/{path:path}", include_in_schema=False)
        @app.get("/assets", include_in_schema=False)
        @app.get("/knowledge", include_in_schema=False)
        @app.get("/knowledge/{path:path}", include_in_schema=False)
        @app.get("/research", include_in_schema=False)
        @app.get("/research/{path:path}", include_in_schema=False)
        @app.get("/insights", include_in_schema=False)
        @app.get("/insights/{path:path}", include_in_schema=False)
        @app.get("/brainstorm", include_in_schema=False)
        @app.get("/brainstorm/{path:path}", include_in_schema=False)
        @app.get("/hot-topics", include_in_schema=False)
        @app.get("/hot-topics/{path:path}", include_in_schema=False)
        @app.get("/inspiration", include_in_schema=False)
        @app.get("/inspiration/{path:path}", include_in_schema=False)
        @app.get("/bookshelf", include_in_schema=False)
        @app.get("/bookshelf/{path:path}", include_in_schema=False)
        @app.get("/agents", include_in_schema=False)
        @app.get("/agents/{path:path}", include_in_schema=False)
        @app.get("/content", include_in_schema=False)
        @app.get("/content/{path:path}", include_in_schema=False)
        @app.get("/data-center", include_in_schema=False)
        @app.get("/data-center/{path:path}", include_in_schema=False)
        @app.get("/platform-data", include_in_schema=False)
        @app.get("/platform-data/{path:path}", include_in_schema=False)
        @app.get("/runs", include_in_schema=False)
        @app.get("/runs/{path:path}", include_in_schema=False)
        @app.get("/documents", include_in_schema=False)
        @app.get("/documents/{path:path}", include_in_schema=False)
        @app.get("/profile", include_in_schema=False)
        @app.get("/settings", include_in_schema=False)
        @app.get("/tenant", include_in_schema=False)
        @app.get("/tenant/{path:path}", include_in_schema=False)
        @app.get("/workspaces", include_in_schema=False)
        @app.get("/workspaces/{path:path}", include_in_schema=False)
        @app.get("/datasets", include_in_schema=False)
        @app.get("/datasets/{path:path}", include_in_schema=False)
        @app.get("/users", include_in_schema=False)
        @app.get("/tenants", include_in_schema=False)
        @app.get("/tenants/{path:path}", include_in_schema=False)
        @app.get("/learning", include_in_schema=False)
        @app.get("/learning/{path:path}", include_in_schema=False)
        @app.get("/m/learning", include_in_schema=False)
        @app.get("/m/learning/{path:path}", include_in_schema=False)
        async def spa_routes(path: str = None):
            # 返回前端index.html
            return FileResponse(index_html)
    else:
        @app.get("/", tags=["系统"])
        async def root():
            """根路径（无前端构建产物时返回 JSON）"""
            return {
                "message": f"Welcome to {settings.app_name}",
                "version": settings.app_version,
                "docs": "/api/docs" if settings.debug else "disabled",
            }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )
