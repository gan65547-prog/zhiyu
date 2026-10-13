from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Annotated, Optional
from pydantic import BaseModel

from api.deps import get_current_superuser
from infrastructure.logging.logger import get_logger

router = APIRouter(prefix="/admin/platform-app-configs", tags=["平台应用配置管理"])
logger = get_logger(__name__)

_COMM_PLATFORMS = frozenset({"feishu", "wecom", "dingtalk"})


class PlatformAppConfigCreate(BaseModel):
    tenant_id: str
    platform: str
    app_id: str
    app_secret: str
    display_name: Optional[str] = None
    verification_token: Optional[str] = None
    encrypt_key: Optional[str] = None
    config: Optional[dict] = None


class PlatformAppConfigUpdate(BaseModel):
    app_secret: Optional[str] = None
    display_name: Optional[str] = None
    verification_token: Optional[str] = None
    encrypt_key: Optional[str] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None


def _get_db(request: Request):
    db = getattr(request.app.state, 'db', None)
    if not db:
        raise HTTPException(status_code=503, detail="数据库连接不可用")
    return db


@router.post("")
async def create_platform_app_config(
    request: Request,
    data: PlatformAppConfigCreate,
    current_user: Annotated[dict, Depends(get_current_superuser)],
    db=Depends(_get_db),
):
    """创建平台应用配置（仅超管）"""
    from apps.integration.services.platform_app_config import PlatformAppConfigService

    service = PlatformAppConfigService(db=db)
    cred_map = {
        "feishu": {"app_secret": data.app_secret},
        "wecom": {"corp_secret": data.app_secret},
        "dingtalk": {"app_secret": data.app_secret},
    }
    credentials = cred_map.get(data.platform, {"app_secret": data.app_secret})

    try:
        result = await service.create_config(
            tenant_id=data.tenant_id,
            platform=data.platform,
            app_id=data.app_id,
            credentials=credentials,
            display_name=data.display_name,
            verification_token=data.verification_token,
            encrypt_key=data.encrypt_key,
            config=data.config,
        )
        return {"code": 0, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.error(f"创建平台应用配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.get("")
async def list_platform_app_configs(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_superuser)],
    db=Depends(_get_db),
):
    """列出所有配置（不含明文凭证）"""
    rows = await db.fetch_all("""
        SELECT id, tenant_id, platform, app_id, display_name,
               is_active, created_at, updated_at
        FROM platform_app_configs ORDER BY created_at DESC
    """)
    return {"code": 0, "data": [dict(r) for r in rows]}


@router.get("/{config_id}")
async def get_platform_app_config(
    config_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_superuser)],
    db=Depends(_get_db),
):
    """获取单个配置（不含 app_secret 明文）"""
    row = await db.fetch_one("""
        SELECT id, tenant_id, platform, app_id, display_name, is_active, created_at
        FROM platform_app_configs WHERE id = :id
    """, {"id": config_id})
    if not row:
        raise HTTPException(404, "配置不存在")
    return {"code": 0, "data": dict(row)}


@router.put("/{config_id}")
async def update_platform_app_config(
    config_id: str,
    data: PlatformAppConfigUpdate,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_superuser)],
    db=Depends(_get_db),
):
    """更新配置"""
    from apps.integration.services.platform_app_config import PlatformAppConfigService

    service = PlatformAppConfigService(db=db)
    kw = {}
    if data.display_name is not None:
        kw["display_name"] = data.display_name
    if data.verification_token is not None:
        kw["verification_token"] = data.verification_token
    if data.encrypt_key is not None:
        kw["encrypt_key"] = data.encrypt_key
    if data.is_active is not None:
        kw["is_active"] = data.is_active
    if data.config is not None:
        kw["config"] = data.config
    if data.app_secret is not None:
        kw["credentials"] = {"app_secret": data.app_secret}

    ok = await service.update_config(config_id, **kw)
    if not ok:
        raise HTTPException(404, "配置不存在")
    return {"code": 0, "msg": "更新成功"}
