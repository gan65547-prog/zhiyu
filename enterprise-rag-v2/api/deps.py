"""
FastAPI 依赖注入

定义API路由的依赖项，包括认证、权限、租户上下文等
"""

from typing import Optional, Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status, Header, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.container import Container, get_container
from core.config import get_settings
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.repositories import (
    TenantRepositoryImpl,
    UserRepositoryImpl,
    WorkspaceRepositoryImpl,
    WorkspaceMemberRepositoryImpl,
    DatasetRepositoryImpl,
    DocumentRepositoryImpl,
    DocumentChunkRepositoryImpl,
    ConversationRepositoryImpl,
    MessageRepositoryImpl,
)
from services.impl import (
    AuthServiceImpl,
    TenantServiceImpl,
    WorkspaceServiceImpl,
    DatasetServiceImpl,
    DocumentServiceImpl,
    ChatServiceImpl,
    UserServiceImpl,
)
from services.interfaces.auth_service import AuthService
from services.interfaces.tenant_service import TenantService
from services.interfaces.workspace_service import WorkspaceService
from services.interfaces.dataset_service import DatasetService
from services.interfaces.document_service import DocumentService
from services.interfaces.chat_service import ChatService
from services.interfaces.user_service import UserService


security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（请求成功时自动提交事务）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_container() -> Container:
    """获取全局依赖注入容器（单例）"""
    from core.container import container as global_container
    return global_container


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> AuthService:
    """获取认证服务"""
    return AuthServiceImpl(session)


def get_tenant_service(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> TenantService:
    """获取租户服务"""
    return TenantServiceImpl(session)


def get_workspace_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> WorkspaceService:
    """获取工作空间服务"""
    quota_svc = getattr(request.app.state, "quota_service", None)
    return WorkspaceServiceImpl(session, quota_service=quota_svc)


def get_dataset_service(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> DatasetService:
    """获取数据集服务"""
    return DatasetServiceImpl(session)


def get_document_service(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> DocumentService:
    """获取文档服务"""
    return DocumentServiceImpl(session)


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_db)]
) -> ChatService:
    """获取对话服务"""
    return ChatServiceImpl(session)


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> UserService:
    """获取用户服务"""
    quota_svc = getattr(request.app.state, "quota_service", None)
    return UserServiceImpl(session, quota_service=quota_svc)


def get_quota_service(request: Request):
    """从应用状态获取自托管资源用量服务。"""
    return getattr(request.app.state, "quota_service", None)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db)],
    access_token_cookie: Annotated[Optional[str], Cookie(alias="access_token")] = None
) -> dict:
    """获取当前登录用户"""
    token = credentials.credentials if credentials else access_token_cookie
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    auth_service = AuthServiceImpl(session)
    payload = await auth_service.verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_active_user(
    current_user: Annotated[dict, Depends(get_current_user)]
) -> dict:
    """获取当前活跃用户"""
    if current_user.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    return current_user


async def get_current_superuser(
    current_user: Annotated[dict, Depends(get_current_active_user)]
) -> dict:
    """获取当前超级管理员用户（仅管理员可访问租户管理）"""
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有系统管理员才能访问租户管理功能"
        )
    
    return current_user


async def require_metrics_access(
    request: Request,
    access_token_cookie: Annotated[Optional[str], Cookie(alias="access_token")] = None
) -> None:
    """Metrics 端点认证：优先校验 Internal API Key，否则回退到用户 JWT 认证"""
    from core.config import get_settings
    settings = get_settings()
    internal_keys = settings.security.internal_api_keys

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:]
        if internal_keys and bearer_token in internal_keys:
            return
    if internal_keys and access_token_cookie in internal_keys:
        return

    from services.impl.auth_service import AuthServiceImpl
    from infrastructure.database.session import AsyncSessionLocal
    token = bearer_token if auth_header.startswith("Bearer ") else access_token_cookie
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    async with AsyncSessionLocal() as session:
        auth_service = AuthServiceImpl(session)
        payload = await auth_service.verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )


def parse_tenant_uuid_from_user(current_user: dict) -> UUID:
    """将 JWT/用户上下文中的 tenant_id 解析为 UUID；非法格式返回 400，缺失返回 403。"""
    raw = current_user.get("tenant_id")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any tenant",
        )
    try:
        if isinstance(raw, UUID):
            return raw
        return UUID(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="令牌中的租户 ID 无效，请重新登录后重试",
        )


async def get_tenant_id(
    current_user: Annotated[dict, Depends(get_current_active_user)]
) -> UUID:
    """获取当前租户ID"""
    return parse_tenant_uuid_from_user(current_user)


async def get_workspace_id(
    workspace_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_tenant_id)],
    container: Annotated[Container, Depends(get_container)]
) -> UUID:
    """验证工作空间ID"""
    async for session in get_db():
        workspace_service = WorkspaceServiceImpl(session)
        workspace = await workspace_service.get_workspace(workspace_id)

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        if str(workspace.get("tenant_id")) != str(tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace does not belong to your tenant"
            )

        return workspace_id


def require_permission(resource_type: str, action: str):
    """权限验证装饰器工厂"""
    async def permission_checker(
        resource_id: UUID,
        current_user: Annotated[dict, Depends(get_current_active_user)],
        container: Annotated[Container, Depends(get_container)]
    ) -> bool:
        """检查用户权限"""
        user_id = UUID(current_user["sub"])

        async for session in get_db():
            auth_service = AuthServiceImpl(session)
            has_permission = await auth_service.verify_permission(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have permission to {action} this {resource_type}"
                )

            return True

    return permission_checker


async def get_pagination(
    page: int = 1,
    page_size: int = 20
) -> dict:
    """获取分页参数"""
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be between 1 and 100"
        )

    return {
        "page": page,
        "page_size": page_size
    }


async def get_request_id(
    x_request_id: Optional[str] = Header(None)
) -> str:
    """获取请求ID"""
    import uuid
    return x_request_id or str(uuid.uuid4())


async def get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"


async def require_tenant_admin(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """要求租户管理员权限（工作空间 OWNER/ADMIN，与 /auth/me 的 is_tenant_admin 一致）"""
    if current_user.get("is_superuser"):
        return

    try:
        user_uuid = UUID(str(current_user["sub"]).strip())
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您需要租户管理员权限才能执行此操作",
        )

    auth = AuthServiceImpl(db)
    if await auth._check_is_tenant_admin(user_uuid):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="您需要租户管理员权限才能执行此操作",
    )


async def require_user_access(
    user_id: str,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """要求用户本人或租户管理员权限"""
    # 用户本人直接通过
    if current_user["sub"] == user_id:
        return
    
    # 检查是否为租户管理员
    try:
        await require_tenant_admin(current_user, db)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问此用户信息"
        )


def _is_ip_allowed(client_ip: str, whitelist: list[str]) -> bool:
    """P0 简化版 IP 白名单：支持精确匹配或 *。空数组拒绝所有 IP。"""
    normalized = {item.strip() for item in whitelist if str(item).strip()}
    if not normalized:
        return False
    if "*" in normalized:
        return True
    return client_ip in normalized


async def get_internal_admin_identity(
    request: Request,
    x_request_id: Annotated[Optional[str], Header(alias="X-Request-Id")] = None,
    x_internal_api_key: Annotated[Optional[str], Header(alias="X-Internal-Api-Key")] = None,
    x_op_id: Annotated[Optional[str], Header(alias="X-Op-Id")] = None,
    x_operator: Annotated[Optional[str], Header(alias="X-Operator")] = None,
) -> dict:
    """
    内部运维接口鉴权（P0）:
    - 必须带 X-Request-Id
    - 必须通过 X-Internal-Api-Key 校验
    - 来源 IP 必须在白名单
    - 写操作必须带 X-Op-Id
    """
    settings = get_settings()
    method = request.method.upper()
    client_ip = await get_client_ip(request)

    if not x_request_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MISSING_REQUEST_ID")

    allowed_keys = {key.strip() for key in settings.security.internal_api_keys if str(key).strip()}
    if not x_internal_api_key or (allowed_keys and x_internal_api_key not in allowed_keys):
        from infrastructure.monitoring.ops_internal_prometheus import (
            INTERNAL_API_KEY_VERIFY_FAILED_TOTAL,
        )

        INTERNAL_API_KEY_VERIFY_FAILED_TOTAL.inc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_INTERNAL_API_KEY")

    if not _is_ip_allowed(client_ip, settings.security.internal_ip_whitelist):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP_NOT_ALLOWED")

    if method in {"POST", "PUT", "PATCH", "DELETE"} and not x_op_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MISSING_OPERATION_ID")
    if method in {"POST", "PUT", "PATCH", "DELETE"} and not x_operator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MISSING_OPERATOR")

    return {
        "request_id": x_request_id,
        "operation_id": x_op_id,
        "operator": x_operator,
        "client_ip": client_ip,
        "method": method,
    }
