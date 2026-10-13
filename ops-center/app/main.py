from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from app.auth.user_store import init_user_store
from app.config import get_settings
from app.db import init_db
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.operations import router as operations_router
from app.routers.tenants import router as tenants_router
from app.routers.users import router as users_router
from app.services.prewarm_service import run_startup_prewarm

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = init_db()
    app.state.ops_db = conn
    init_user_store(conn)
    app.state.prewarm_status = {"total": 0, "warmed": 0, "failed": 0, "failures": [], "ok": False}
    try:
        app.state.prewarm_status = await run_startup_prewarm()
    except Exception as e:
        print(f"Prewarm failed: {e}")
    try:
        yield
    finally:
        conn.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ops-center",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.include_router(health_router, tags=["System"])
    app.include_router(auth_router, tags=["Auth"])
    app.include_router(users_router, tags=["Users"])
    app.include_router(tenants_router, tags=["Operations"])
    app.include_router(operations_router, tags=["Operations"])

    index_html = _STATIC_DIR / "index.html"
    vue_console = _STATIC_DIR / "console"
    if (vue_console / "index.html").is_file():
        app.mount(
            "/console",
            StaticFiles(directory=str(vue_console), html=True),
            name="ops_console",
        )

    @app.get("/")
    async def root():
        """简易 Web 控制台（登录 + 文档入口）；无静态文件时回退 JSON。"""
        if index_html.is_file():
            return FileResponse(index_html)
        return {
            "service": settings.app_name,
            "env": settings.app_env,
            "message": "ops-center is running",
        }

    return app


app = create_app()
