"""
认证路由

处理用户注册、登录、登出等认证相关的API端点
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Cookie
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.schemas.auth import UserRegister, UserLogin, RefreshTokenRequest, PasswordChange
from api.deps import get_auth_service, get_current_active_user, get_client_ip, get_db
from services.interfaces.auth_service import AuthService
from services.impl.auth_service import AuthServiceImpl
from core.config import get_settings
from infrastructure.logging.logger import get_logger
from infrastructure.database.models import UserAPIKey, UserConfig, ThemeMode, Language, Tenant
from services.impl.content_credential_service import CredentialVault
from services.utils.jwt import create_access_token, create_refresh_token
from services.audit.service import AuditAction, AuditService


router = APIRouter()
settings = get_settings()
ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
logger = get_logger(__name__)


def _cookie_secure() -> bool:
    return settings.environment.lower() in {"production", "staging"}


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=settings.auth.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=settings.auth.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/", samesite="lax")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/", samesite="lax")


class RegisterResponse(BaseModel):
    success: bool = True
    message: str = "User registered successfully"
    data: dict


class LoginResponse(BaseModel):
    success: bool = True
    message: str = "Login successful"
    data: dict


class RefreshTokenResponse(BaseModel):
    success: bool = True
    message: str = "Token refreshed successfully"
    data: dict


class LogoutResponse(BaseModel):
    success: bool = True
    message: str = "Logout successful"
    data: dict = {"logged_out": True}


class ChangePasswordResponse(BaseModel):
    success: bool = True
    message: str = "Password changed successfully"
    data: dict = {"changed": True}


class UserConfigPayload(BaseModel):
    """当前用户的工作台配置。密钥等敏感信息不属于此接口。"""

    theme: str = "light"
    language: str = "zh-CN"
    default_page: str = "/"
    embedding_model: str = "bge-small-zh-v1.5"
    llm_model: str = "deepseek-chat"
    temperature: float = 0.7
    top_k: int = 5
    session_timeout_minutes: int = 1440
    two_factor_auth_enabled: bool = False
    ip_whitelist: str = ""


class UserAPIKeyCreatePayload(BaseModel):
    provider: str
    name: str
    api_key: str
    base_url: str | None = None
    is_default: bool = False


class TenantContextSwitchPayload(BaseModel):
    tenant_id: str


def _config_to_dict(config: UserConfig) -> dict:
    return {
        "theme": getattr(config.theme, "value", config.theme),
        "language": getattr(config.language, "value", config.language),
        "default_page": config.default_page,
        "embedding_model": config.embedding_model,
        "llm_model": config.llm_model,
        "temperature": config.temperature,
        "top_k": config.top_k,
        "session_timeout_minutes": config.session_timeout_minutes,
        "two_factor_auth_enabled": config.two_factor_auth_enabled,
        "ip_whitelist": config.ip_whitelist or "",
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def _api_key_to_dict(item: UserAPIKey) -> dict:
    return {
        "id": str(item.id),
        "provider": item.provider,
        "name": item.name,
        "base_url": item.base_url or "",
        "is_active": item.is_active,
        "is_default": item.is_default,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "configured": True,
    }


@router.post("/me/tenant-context")
async def switch_tenant_context(
    payload: TenantContextSwitchPayload,
    request: Request,
    response: Response,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """切换超级管理员的租户数据上下文，并重新签发会话 Cookie。"""
    if not current_user.get("is_superuser"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅超级管理员可以切换租户上下文")
    from uuid import UUID

    try:
        tenant_id = UUID(payload.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="租户 ID 无效") from exc

    tenant = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户不存在")
    if getattr(tenant.status, "value", tenant.status) not in {"active", "trial"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="目标租户当前不可用")

    from uuid import UUID
    previous_tenant_id = current_user.get("tenant_id")
    await AuditService(session).log(
        action=AuditAction.TENANT_CONTEXT_SWITCH,
        tenant_id=tenant_id,
        user_id=UUID(current_user["sub"]),
        resource_type="tenant_context",
        resource_id=str(tenant_id),
        details={
            "previous_tenant_id": str(previous_tenant_id) if previous_tenant_id else None,
            "target_tenant_id": str(tenant_id),
        },
        ip_address=await get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    claims = {
        "sub": str(current_user["sub"]),
        "username": current_user.get("username", ""),
        "email": current_user.get("email", ""),
        "tenant_id": str(tenant_id),
        "is_superuser": True,
        "is_tenant_admin": True,
    }
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token({"sub": str(current_user["sub"])})
    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "success": True,
        "data": {
            "tenant_id": str(tenant_id),
            "tenant_name": tenant.name,
        },
    }


@router.get("/me/api-keys")
async def list_my_api_keys(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """只返回脱敏的密钥元数据，绝不返回明文或密文。"""
    from uuid import UUID

    result = await session.execute(
        select(UserAPIKey)
        .where(UserAPIKey.user_id == UUID(current_user["sub"]), UserAPIKey.is_active.is_(True))
        .order_by(UserAPIKey.created_at.desc())
    )
    return {"success": True, "data": [_api_key_to_dict(item) for item in result.scalars().all()]}


@router.post("/me/api-keys", status_code=status.HTTP_201_CREATED)
async def create_my_api_key(
    payload: UserAPIKeyCreatePayload,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """加密保存第三方 API 密钥；创建后也只返回脱敏元数据。"""
    from uuid import UUID

    provider = payload.provider.strip().lower()
    name = payload.name.strip()
    api_key = payload.api_key.strip()
    if not provider or len(provider) > 50:
        raise HTTPException(status_code=422, detail="provider 必须填写且不超过 50 个字符")
    if provider not in {"deepseek", "openai", "ollama"}:
        raise HTTPException(status_code=422, detail="当前仅支持 deepseek、openai、ollama Provider")
    if not name or len(name) > 100:
        raise HTTPException(status_code=422, detail="名称必须填写且不超过 100 个字符")
    if not api_key or len(api_key) > 1000:
        raise HTTPException(status_code=422, detail="API Key 必须填写且不超过 1000 个字符")
    base_url = payload.base_url.strip() if payload.base_url else None
    if base_url and len(base_url) > 500:
        raise HTTPException(status_code=422, detail="Base URL 不超过 500 个字符")
    try:
        encrypted = CredentialVault().encrypt({"api_key": api_key})
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user_id = UUID(current_user["sub"])
    if payload.is_default:
        defaults = await session.execute(select(UserAPIKey).where(UserAPIKey.user_id == user_id, UserAPIKey.is_active.is_(True)))
        for item in defaults.scalars().all():
            item.is_default = False
    item = UserAPIKey(
        user_id=user_id,
        provider=provider,
        name=name,
        api_key_encrypted=encrypted,
        base_url=base_url,
        is_active=True,
        is_default=payload.is_default,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return {"success": True, "data": _api_key_to_dict(item)}


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_api_key(
    key_id: str,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    from uuid import UUID

    try:
        parsed_id = UUID(key_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="API Key 不存在") from exc
    item = await session.scalar(select(UserAPIKey).where(UserAPIKey.id == parsed_id, UserAPIKey.user_id == UUID(current_user["sub"]), UserAPIKey.is_active.is_(True)))
    if item is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    item.is_active = False
    item.is_default = False
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/config")
async def get_my_config(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """读取当前用户的工作台配置，首次访问时创建默认记录。"""
    from uuid import UUID

    user_id = UUID(current_user["sub"])
    result = await session.execute(select(UserConfig).where(UserConfig.user_id == user_id))
    config = result.scalar_one_or_none()
    if config is None:
        config = UserConfig(user_id=user_id)
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return {"success": True, "data": _config_to_dict(config)}


@router.put("/me/config")
async def update_my_config(
    payload: UserConfigPayload,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """持久化当前用户的工作台偏好；不修改服务端环境模型或密钥。"""
    from uuid import UUID

    if payload.theme not in {item.value for item in ThemeMode}:
        raise HTTPException(status_code=422, detail="theme 必须是 light、dark 或 auto")
    if payload.language not in {item.value for item in Language}:
        raise HTTPException(status_code=422, detail="language 必须是 zh-CN 或 en-US")
    if not 0 <= payload.temperature <= 1:
        raise HTTPException(status_code=422, detail="temperature 必须在 0 到 1 之间")
    if not 1 <= payload.top_k <= 50:
        raise HTTPException(status_code=422, detail="top_k 必须在 1 到 50 之间")
    if not 5 <= payload.session_timeout_minutes <= 10080:
        raise HTTPException(status_code=422, detail="session_timeout_minutes 必须在 5 分钟到 7 天之间")

    user_id = UUID(current_user["sub"])
    result = await session.execute(select(UserConfig).where(UserConfig.user_id == user_id))
    config = result.scalar_one_or_none()
    if config is None:
        config = UserConfig(user_id=user_id)
        session.add(config)

    config.theme = ThemeMode(payload.theme)
    config.language = Language(payload.language)
    config.default_page = payload.default_page[:100]
    config.embedding_model = payload.embedding_model[:255]
    config.llm_model = payload.llm_model[:255]
    config.temperature = payload.temperature
    config.top_k = payload.top_k
    config.session_timeout_minutes = payload.session_timeout_minutes
    config.two_factor_auth_enabled = payload.two_factor_auth_enabled
    config.ip_whitelist = payload.ip_whitelist[:4000] if payload.ip_whitelist else None
    await session.commit()
    await session.refresh(config)
    return {"success": True, "message": "工作台配置已保存", "data": _config_to_dict(config)}


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    req: UserRegister,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str, Depends(get_client_ip)]
):
    """用户注册"""
    try:
        user_agent = request.headers.get("user-agent", "")
        
        result = await auth_service.register(
            username=req.name,
            email=req.email,
            password=req.password,
            ip_address=client_ip,
            user_agent=user_agent
        )
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])

        return RegisterResponse(
            success=True,
            message="User registered successfully",
            data=result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Registration failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    req: UserLogin,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str, Depends(get_client_ip)]
):
    """用户登录"""
    if settings.security.disable_default_admin_login and req.email.lower() == "admin@default.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Default admin login is disabled"
        )
    try:
        user_agent = request.headers.get("user-agent", "")
        
        result = await auth_service.login(
            username=req.email,
            password=req.password,
            ip_address=client_ip,
            user_agent=user_agent
        )
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])

        return LoginResponse(
            success=True,
            message="Login successful",
            data=result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Login failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    request: Optional[RefreshTokenRequest] = None,
    refresh_token_cookie: Annotated[Optional[str], Cookie(alias=REFRESH_COOKIE_NAME)] = None
):
    """刷新访问令牌"""
    try:
        token_value = request.refresh_token if request and request.refresh_token else refresh_token_cookie
        if not token_value:
            raise ValueError("缺少刷新令牌")
        result = await auth_service.refresh_token(
            refresh_token=token_value
        )
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])

        return RefreshTokenResponse(
            success=True,
            message="Token refreshed successfully",
            data=result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Refresh token failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str, Depends(get_client_ip)]
):
    """用户登出"""
    try:
        from uuid import UUID
        user_id = UUID(current_user["sub"])
        access_token = current_user.get("token", "")

        await auth_service.logout(
            user_id=user_id,
            access_token=access_token,
            ip_address=client_ip
        )
        _clear_auth_cookies(response)

        return LogoutResponse(
            success=True,
            message="Logout successful",
            data={"logged_out": True}
        )
    except (ValueError, TypeError, AttributeError, RuntimeError) as e:
        logger.exception("Logout failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: Request,
    req: PasswordChange,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str, Depends(get_client_ip)]
):
    """修改密码"""
    try:
        from uuid import UUID
        user_id = UUID(current_user["sub"])

        success = await auth_service.change_password(
            user_id=user_id,
            old_password=req.old_password,
            new_password=req.new_password,
            ip_address=client_ip
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Old password is incorrect"
            )

        return ChangePasswordResponse(
            success=True,
            message="Password changed successfully",
            data={"changed": True}
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Change password failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.get("/me")
async def get_user_info(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)]
):
    """获取当前用户信息"""
    try:
        from uuid import UUID
        from infrastructure.repositories import UserRepositoryImpl
        
        user_id = UUID(current_user["sub"])

        auth_impl = AuthServiceImpl(session)
        is_tenant_admin = await auth_impl._check_is_tenant_admin(user_id)

        user_repo = UserRepositoryImpl(session)
        user = await user_repo.get_by_id(user_id)
        
        if user:
            user_data = {
                "id": str(user.id),
                "name": user.username,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "is_tenant_admin": is_tenant_admin,
                "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                "current_workspace_id": str(user.current_workspace_id) if user.current_workspace_id else None,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
        else:
            current_user["is_tenant_admin"] = is_tenant_admin
            user_data = current_user
        
        return {
            "success": True,
            "message": "User info retrieved successfully",
            "data": user_data
        }
    except (ValueError, RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to get current user info: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
