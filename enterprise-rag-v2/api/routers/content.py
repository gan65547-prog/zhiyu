"""内容中心 API。"""

from datetime import datetime
import base64
import hashlib
import json
import secrets
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.content import ContentConnectorResponse, ContentCredentialCreateRequest, ContentCredentialResponse, ContentCredentialTestResponse, ContentDraftCreateRequest, ContentDraftFromResearchRequest, ContentDraftListResponse, ContentDraftResponse, ContentDraftReviewRequest, ContentDraftRewriteRequest, ContentDraftUpdateRequest, ContentMetricCreateRequest, ContentMetricImportRequest, ContentMetricImportResponse, ContentMetricListResponse, ContentMetricSyncCreateRequest, ContentMetricSyncListResponse, ContentMetricSyncResponse, ContentPublishConfirmRequest, ContentPublishListResponse, ContentPublishRequest, ContentPublishResponse, ContentRetrospectiveResponse, ContentScheduleRequest, ContentTopicCreateRequest, ContentTopicListResponse, ContentTopicResponse, XOAuthCompleteRequest
from services.impl.content_service import ContentService
from services.impl.content_generation_service import ContentGenerationService
from services.impl.content_connector_registry import ContentConnectorRegistry
from services.impl.content_publishing_service import ContentPublishingService
from services.impl.content_credential_service import ContentCredentialService
from services.impl.content_metric_sync_service import ContentMetricSyncService
from infrastructure.database.models import ContentMetricSyncRun
from infrastructure.queue.content_tasks import sync_metric_snapshot
from infrastructure.cache import get_redis
from core.config import get_settings
from services.oauth.x_provider import XOAuthProvider

router = APIRouter()

_X_OAUTH_STATE_TTL_SECONDS = 600


def _x_oauth_state_key(state: str) -> str:
    return f"oauth:x:pkce:{state}"


async def _x_oauth_redis():
    try:
        return await get_redis()
    except (RuntimeError, OSError, TypeError, ValueError):
        return None


def _x_provider() -> XOAuthProvider:
    settings = get_settings()
    return XOAuthProvider(
        client_id=settings.x_oauth_client_id,
        client_secret=settings.x_oauth_client_secret,
        scopes=settings.x_oauth_scopes,
    )


@router.get("/oauth/x/start")
async def start_x_oauth(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """创建一次性 X OAuth PKCE 授权 URL；不返回或保存第三方 token。"""
    settings = get_settings()
    provider = _x_provider()
    if not provider.configured or not settings.x_oauth_redirect_uri.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "X_OAUTH_NOT_CONFIGURED", "message": "X OAuth 尚未配置 Client ID、scopes 或回调地址"},
        )
    tenant_id = parse_tenant_uuid_from_user(current_user)
    user_id = _user_id(current_user)
    try:
        await ContentCredentialService(db).access._verify_workspace_access(
            workspace_id, tenant_id, user_id, bool(current_user.get("is_superuser"))
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    redis_client = await _x_oauth_redis()
    if redis_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OAuth state 存储暂不可用")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    await redis_client.setex(
        _x_oauth_state_key(state),
        _X_OAUTH_STATE_TTL_SECONDS,
        json.dumps({
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "workspace_id": str(workspace_id),
            "redirect_uri": settings.x_oauth_redirect_uri.strip(),
            "code_verifier": verifier,
        }, ensure_ascii=False),
    )
    return {
        "success": True,
        "data": {"url": provider.authorization_url(redirect_uri=settings.x_oauth_redirect_uri.strip(), state=state, code_challenge=challenge)},
    }


@router.post("/oauth/x/complete")
async def complete_x_oauth(
    request: XOAuthCompleteRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    """消费一次性 state，换取 X 用户令牌并加密保存到绑定 workspace。"""
    redis_client = await _x_oauth_redis()
    if redis_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OAuth state 存储暂不可用")
    raw_state = await redis_client.getdel(_x_oauth_state_key(request.state))
    if not raw_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state 已过期、已消费或无效")
    try:
        state_data = json.loads(raw_state)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state 格式无效") from exc

    user_id = _user_id(current_user)
    if str(state_data.get("user_id")) != str(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OAuth state 不属于当前用户")
    current_tenant_id = parse_tenant_uuid_from_user(current_user)
    if str(state_data.get("tenant_id")) != str(current_tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OAuth state 不属于当前租户")
    settings = get_settings()
    redirect_uri = str(state_data.get("redirect_uri") or "")
    if not redirect_uri or redirect_uri != settings.x_oauth_redirect_uri.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth 回调地址不匹配")

    provider = _x_provider()
    token_result = await provider.exchange_code(code=request.code, redirect_uri=redirect_uri, code_verifier=str(state_data.get("code_verifier") or ""))
    if token_result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X OAuth 授权码交换失败")
    access_token = str(token_result.get("access_token") or "")
    user_info = await provider.get_user(access_token)
    if user_info.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X OAuth 用户信息读取失败")

    workspace_id = UUID(str(state_data["workspace_id"]))
    tenant_id = UUID(str(state_data["tenant_id"]))
    try:
        await ContentCredentialService(db).access._verify_workspace_access(
            workspace_id, tenant_id, user_id, bool(current_user.get("is_superuser"))
        )
        safe_credential = await ContentCredentialService(db).create(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            user_id=user_id,
            is_superuser=bool(current_user.get("is_superuser")),
            platform="x",
            name=f"X OAuth · {user_info.get('username') or user_info.get('name') or user_info['id']}",
            hint="OAuth 用户令牌（已加密）",
            credentials={
                "access_token": access_token,
                "refresh_token": token_result.get("refresh_token"),
                "token_type": token_result.get("token_type", "bearer"),
                "expires_in": token_result.get("expires_in"),
                "provider_user_id": str(user_info["id"]),
                "provider_username": user_info.get("username"),
            },
        )
        await db.commit()
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"success": True, "message": "X OAuth 已授权并加密保存", "data": {"credential": safe_credential, "provider_user_id": str(user_info["id"])}}


@router.get("/connectors", response_model=list[ContentConnectorResponse])
async def list_connectors(current_user: Annotated[dict, Depends(get_current_active_user)]):
    return ContentConnectorRegistry().describe()


@router.get("/credentials", response_model=list[ContentCredentialResponse])
async def list_credentials(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        return await ContentCredentialService(db).list(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/credentials", response_model=ContentCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(request: ContentCredentialCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentCredentialService(db).create(workspace_id=request.workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), platform=request.platform, name=request.name, credentials=request.credentials, hint=request.credential_hint)
        await db.commit()
        return result
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/credentials/{credential_id}", response_model=ContentCredentialResponse)
async def revoke_credential(credential_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentCredentialService(db).revoke(credential_id=credential_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
        if result is None: raise HTTPException(status_code=404, detail="内容平台凭据不存在")
        await db.commit()
        return result
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/credentials/{credential_id}/test", response_model=ContentCredentialTestResponse)
async def test_credential(credential_id: UUID, workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentCredentialService(db).test(credential_id=credential_id, workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
        if result is None:
            raise HTTPException(status_code=404, detail="内容平台凭据不存在或已撤销")
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _user_id(current_user: dict) -> UUID:
    try: return UUID(str(current_user["sub"]))
    except (KeyError, ValueError, TypeError) as exc: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.post("/topics", response_model=ContentTopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(request: ContentTopicCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentService(db).create_topic(tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump()); await db.commit(); return result
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/topics", response_model=ContentTopicListResponse)
async def list_topics(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        items = await ContentService(db).list_topics(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser"))); return {"items": items, "total": len(items)}
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/drafts", response_model=ContentDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(request: ContentDraftCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentService(db).create_draft(tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump()); await db.commit(); return result
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/drafts/from-research/{report_id}", response_model=ContentDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft_from_research(report_id: UUID, request: ContentDraftFromResearchRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentGenerationService(db).create_draft_from_report(
            report_id=report_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
            title=request.title,
            topic_id=request.topic_id,
        )
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="研究报告不存在或无权访问")
    await db.commit()
    return result


@router.put("/drafts/{draft_id}", response_model=ContentDraftResponse)
async def update_draft(draft_id: UUID, request: ContentDraftUpdateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).update_draft(draft_id=draft_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump(exclude_unset=True))
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="内容草稿不存在")
    await db.commit(); return result


@router.get("/drafts", response_model=ContentDraftListResponse)
async def list_drafts(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db), review_status: Optional[str] = Query(None)):
    try:
        items = await ContentService(db).list_drafts(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), review_status=review_status); return {"items": items, "total": len(items)}
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/rewrite", response_model=ContentDraftResponse)
async def rewrite_draft(draft_id: UUID, request: ContentDraftRewriteRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentService(db).rewrite_draft(
            draft_id=draft_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), platforms=request.platforms,
            mode=request.mode, provider=request.provider, max_tokens=request.max_tokens,
        )
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="内容草稿不存在")
    await db.commit(); return result


@router.post("/drafts/{draft_id}/review", response_model=ContentDraftResponse)
async def review_draft(draft_id: UUID, request: ContentDraftReviewRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentService(db).review_draft(draft_id=draft_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), status=request.status)
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="内容草稿不存在")
    await db.commit(); return result


@router.post("/drafts/{draft_id}/publish", response_model=ContentPublishResponse)
async def publish_draft(draft_id: UUID, request: ContentPublishRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).publish_draft(draft_id=draft_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump())
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="内容草稿不存在")
    await db.commit(); return result


@router.post("/drafts/{draft_id}/schedule", response_model=ContentPublishResponse, status_code=status.HTTP_201_CREATED)
async def schedule_draft(draft_id: UUID, request: ContentScheduleRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).schedule_draft(draft_id=draft_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump())
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="内容草稿不存在")
    await db.commit(); return result


@router.post("/publishes/{publish_id}/confirm", response_model=ContentPublishResponse)
async def confirm_publish(publish_id: UUID, request: ContentPublishConfirmRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).confirm_publish(publish_id=publish_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump())
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="发布记录不存在")
    await db.commit(); return result


@router.post("/publishes/{publish_id}/metrics", response_model=ContentPublishResponse)
async def add_metric(publish_id: UUID, request: ContentMetricCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).add_metric(publish_id=publish_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), data=request.model_dump())
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="发布记录不存在")
    await db.commit(); return result


@router.get("/publishes", response_model=ContentPublishListResponse)
async def list_publishes(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db), from_date: Optional[datetime] = Query(None), to_date: Optional[datetime] = Query(None)):
    try:
        items = await ContentService(db).list_publishes(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), from_date=from_date, to_date=to_date)
        return {"items": items, "total": len(items)}
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/publishes/metrics", response_model=ContentMetricListResponse)
async def list_metrics(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db), limit: int = Query(500, ge=1, le=1000)):
    try:
        items = await ContentService(db).list_metrics(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), limit=limit)
        return {"items": items, "total": len(items)}
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/publishes/metrics/import", response_model=ContentMetricImportResponse)
async def import_metrics(request: ContentMetricImportRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentService(db).import_metrics(
            workspace_id=request.workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")),
            items=[item.model_dump() for item in request.items],
        )
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return result


@router.post("/publishes/metrics/sync", response_model=ContentMetricSyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_metric_sync(request: ContentMetricSyncCreateRequest, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentMetricSyncService(db).create(
            workspace_id=request.workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")), platform=request.platform, credential_id=request.credential_id,
            items=[item.model_dump(mode="json") for item in request.items],
        )
        await db.commit()
        try:
            task = sync_metric_snapshot.delay(str(result["id"]))
            run = await db.get(ContentMetricSyncRun, str(result["id"]))
            if run is not None:
                run.task_id = str(task.id)
                await db.commit()
            result["task_id"] = str(task.id)
        except Exception as exc:
            run = await db.get(ContentMetricSyncRun, str(result["id"]))
            if run is not None:
                run.status = "failed"; run.error_message = f"同步任务投递失败: {exc}"[:1000]; await db.commit()
            result["status"] = "failed"; result["error_message"] = "同步任务投递失败，请稍后重试"
        return result
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishes/metrics/sync", response_model=ContentMetricSyncListResponse)
async def list_metric_sync(workspace_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        items = await ContentMetricSyncService(db).list(workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
        return {"items": items, "total": len(items)}
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/publishes/metrics/sync/{run_id}", response_model=ContentMetricSyncResponse)
async def get_metric_sync(run_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentMetricSyncService(db).get(run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="同步任务不存在")
    return result


@router.post("/publishes/metrics/sync/{run_id}/retry", response_model=ContentMetricSyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_metric_sync(run_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try:
        result = await ContentMetricSyncService(db).retry(
            run_id=run_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
        if result is None: raise HTTPException(status_code=404, detail="同步任务不存在")
        await db.commit()
        try:
            task = sync_metric_snapshot.delay(str(run_id))
            run = await db.get(ContentMetricSyncRun, str(run_id))
            if run is not None:
                run.task_id = str(task.id)
                await db.commit()
            result["task_id"] = str(task.id)
        except Exception as exc:
            run = await db.get(ContentMetricSyncRun, str(run_id))
            if run is not None:
                run.status = "failed"
                run.error_message = f"重试任务投递失败: {exc}"[:1000]
                await db.commit()
            result["status"] = "failed"
            result["error_message"] = "重试任务投递失败，请稍后重试"
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/publishes/{publish_id}/retrospective", response_model=ContentRetrospectiveResponse)
async def create_retrospective(publish_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).create_retrospective(publish_id=publish_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="发布记录不存在")
    await db.commit(); return result


@router.get("/publishes/{publish_id}/retrospective", response_model=ContentRetrospectiveResponse)
async def get_retrospective(publish_id: UUID, current_user: Annotated[dict, Depends(get_current_active_user)], db=Depends(get_db)):
    try: result = await ContentService(db).get_retrospective(publish_id=publish_id, tenant_id=parse_tenant_uuid_from_user(current_user), user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")))
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="复盘记录不存在")
    return result
