"""
OAuth路由

处理第三方OAuth登录的API端点
"""

from fastapi import APIRouter, HTTPException, status, Query, Request
from pydantic import BaseModel

from services.oauth.service import OAuthServiceImpl, OAuthServiceFactory
from services.utils.jwt import decode_token
from infrastructure.logging.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)

_COMM_OAUTH_PROVIDERS = frozenset({"feishu", "wechat_work"})


class OAuthUrlRequest(BaseModel):
    provider: str
    redirect_uri: str


class OAuthCallbackRequest(BaseModel):
    provider: str
    code: str
    redirect_uri: str
    state: str = None


class OAuthLinkRequest(BaseModel):
    provider: str
    code: str
    redirect_uri: str


@router.get("/url")
async def get_oauth_url(
    request: Request,
    provider: str = Query(..., description="OAuth provider: feishu, wechat_work"),
    redirect_uri: str = Query(..., description="OAuth callback URI")
):
    """获取OAuth授权URL"""
    oauth_service = OAuthServiceFactory.get_instance()
    oauth_provider = oauth_service.get_provider(provider)

    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )

    if provider in _COMM_OAUTH_PROVIDERS:
        token = None
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
        if not token:
            token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "AUTH_REQUIRED",
                    "message": "飞书/企业微信 OAuth 需先登录，请在请求头携带 Authorization: Bearer <token> 或使用 Cookie access_token",
                },
            )
        payload = decode_token(token)
        if not payload or payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的访问令牌",
            )
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号未绑定租户，无法使用企业通信类 OAuth",
            )

    state = oauth_service.generate_state()
    url = await oauth_provider.get_authorization_url(redirect_uri, state)

    return {
        "success": True,
        "data": {
            "url": url,
            "state": state
        }
    }


@router.post("/callback")
async def oauth_callback(
    request: OAuthCallbackRequest
):
    """OAuth授权回调"""
    oauth_service = OAuthServiceFactory.get_instance()

    try:
        result = await oauth_service.authenticate_with_oauth(
            provider=request.provider,
            code=request.code,
            redirect_uri=request.redirect_uri
        )

        return {
            "success": True,
            "message": "OAuth authentication successful",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("OAuth callback failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed"
        )


@router.post("/link")
async def link_oauth_account(
    request: Request,
    request_body: OAuthLinkRequest,
    user_id: str = Query(...)
):
    """关联OAuth账户"""
    oauth_service = OAuthServiceFactory.get_instance()

    if request_body.provider in _COMM_OAUTH_PROVIDERS:
        db = getattr(request.app.state, "db", None)
        if db:
            row = await db.fetch_one(
                "SELECT tenant_id FROM users WHERE id = :id",
                {"id": user_id},
            )
            tid = row["tenant_id"] if row else None

    try:
        result = await oauth_service.authenticate_with_oauth(
            provider=request_body.provider,
            code=request_body.code,
            redirect_uri=request_body.redirect_uri
        )

        from uuid import UUID
        success = await oauth_service.link_oauth_account(
            user_id=UUID(user_id),
            provider=request_body.provider,
            provider_user_id=result.get("provider_user_id", "")
        )

        return {
            "success": success,
            "message": "OAuth account linked successfully" if success else "Failed to link OAuth account"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Link OAuth account failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link OAuth account"
        )


@router.delete("/unlink")
async def unlink_oauth_account(
    user_id: str = Query(...),
    provider: str = Query(...)
):
    """取消OAuth关联"""
    oauth_service = OAuthServiceFactory.get_instance()

    try:
        from uuid import UUID
        success = await oauth_service.unlink_oauth_account(
            user_id=UUID(user_id),
            provider=provider
        )

        return {
            "success": success,
            "message": "OAuth account unlinked successfully" if success else "Failed to unlink OAuth account"
        }
    except (ValueError, RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Unlink OAuth account failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlink OAuth account"
        )


@router.get("/linked")
async def get_linked_accounts(
    user_id: str = Query(...)
):
    """获取用户关联的OAuth账户"""
    oauth_service = OAuthServiceFactory.get_instance()

    try:
        from uuid import UUID
        accounts = await oauth_service.get_linked_accounts(UUID(user_id))

        return {
            "success": True,
            "data": accounts
        }
    except (ValueError, RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Get linked OAuth accounts failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get linked accounts"
        )
