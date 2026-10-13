"""
对话路由

处理对话和RAG查询相关的API端点（支持会话权限管理）
"""

import traceback
import json
from typing import Annotated, List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from celery.result import AsyncResult

from api.schemas.base import BaseResponse
from api.schemas.chat import (
    ChatRequest,
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationQueryRequest,
    AdminConversationQueryRequest,
    ConversationInfo,
    MessageInfo,
    ConversationVisibilityEnum,
)
from api.deps import get_chat_service, get_current_active_user, get_quota_service, get_document_service
from apps.commercialization.models import QuotaExceededError
from services.interfaces.chat_service import ChatService
from services.interfaces.document_service import DocumentService
from core.value_objects.pagination import Pagination
from services.permission_checker import PermissionChecker, PermissionAction
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.chat_tasks import process_chat_async_task
from core.rag_config import get_rag_config, is_effective_openai_api_key


router = APIRouter()


@router.get("/readiness")
async def chat_readiness(
    dataset_id: UUID,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """返回知识库是否真的具备可问答上下文，避免把空库误报为模型故障。"""
    user_id = str(current_user["sub"])
    tenant_id = current_user.get("tenant_id")
    await chat_service.verify_dataset_access(dataset_id=dataset_id, user_id=user_id, tenant_id=tenant_id)
    counts = await document_service.get_dataset_document_counts(dataset_id)
    completed = counts["completed"]
    processing = counts["processing"]
    failed = counts["failed"]
    config = get_rag_config()
    provider = str(config.llm_provider or "").lower()
    provider_ready = provider == "ollama" or is_effective_openai_api_key(config.deepseek_api_key)
    reasons: list[str] = []
    actions: list[str] = []
    if completed == 0:
        if processing:
            reasons.append("资料仍在解析和索引")
            actions.append("等待处理完成")
        elif failed:
            reasons.append("资料索引失败")
            actions.append("重试失败资料")
        else:
            reasons.append("知识库还没有已索引资料")
            actions.append("导入资料")
    if not provider_ready:
        reasons.append("模型服务尚未配置有效凭据")
        actions.append("检查模型配置")
    return {
        "ready": bool(completed and provider_ready),
        "indexed_documents": int(completed),
        "processing_documents": int(processing),
        "failed_documents": int(failed),
        "provider": provider,
        "provider_status": "healthy" if provider_ready else "not_configured",
        "reasons": reasons,
        "actions": actions,
    }

logger = get_logger(__name__)

# 权限检查器实例
permission_checker = PermissionChecker()
CHAT_JOB_OWNER_TTL_SECONDS = 24 * 60 * 60
_chat_job_owner_cache: dict[str, dict[str, str]] = {}
_chat_job_cache_insert_times: dict[str, float] = {}


def _purge_expired_chat_job_cache() -> None:
    """清理过期的内存缓存条目（Redis 不可用时防止无限增长）"""
    import time
    now = time.time()
    expired = [k for k, ts in _chat_job_cache_insert_times.items() if now - ts > CHAT_JOB_OWNER_TTL_SECONDS]
    for k in expired:
        _chat_job_owner_cache.pop(k, None)
        _chat_job_cache_insert_times.pop(k, None)


def _chat_job_owner_key(job_id: str) -> str:
    return f"chat_job_owner:{job_id}"


async def _assert_conversation_can_be_updated(
    conversation_id: Optional[UUID], user_id: str
) -> None:
    """防止聊天请求借用他人的会话 ID 写入消息。"""
    if not conversation_id:
        return
    from infrastructure.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        allowed = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.UPDATE,
            session=session,
        )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


async def _get_job_owner_redis(request: Request):
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        return redis_client
    try:
        from infrastructure.cache import get_redis
        redis_client = await get_redis()
        if redis_client:
            setattr(request.app.state, "redis", redis_client)
    except (RuntimeError, ValueError, TypeError, AttributeError):
        redis_client = None
    return redis_client


async def _bind_chat_job_owner(request: Request, job_id: str, user_id: str, tenant_id: Optional[str]) -> None:
    payload = {"user_id": user_id, "tenant_id": tenant_id or ""}
    redis_client = await _get_job_owner_redis(request)
    if redis_client:
        try:
            await redis_client.setex(_chat_job_owner_key(job_id), CHAT_JOB_OWNER_TTL_SECONDS, json.dumps(payload))
            return
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("写入聊天任务归属失败，回退内存缓存: job=%s error=%s", job_id, e, exc_info=True)
    _chat_job_owner_cache[job_id] = payload
    _chat_job_cache_insert_times[job_id] = __import__("time").time()


async def _assert_chat_job_owner(request: Request, job_id: str, user_id: str) -> None:
    payload: Optional[dict[str, str]] = None
    redis_client = await _get_job_owner_redis(request)
    if redis_client:
        try:
            raw = await redis_client.get(_chat_job_owner_key(job_id))
            if raw:
                payload = json.loads(raw)
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("读取聊天任务归属失败，尝试内存缓存: job=%s error=%s", job_id, e, exc_info=True)
    if payload is None:
        _purge_expired_chat_job_cache()
        payload = _chat_job_owner_cache.get(job_id)
    if not payload or str(payload.get("user_id", "")) != str(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


@router.post("/")
async def chat(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    quota_service: Annotated[Any, Depends(get_quota_service)],
):
    """发送对话请求"""
    try:
        # 验证dataset是否属于用户有权访问的workspace
        dataset_id = UUID(request.dataset_id)
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")
        conversation_id = UUID(request.conversation_id) if request.conversation_id else None

        await _assert_conversation_can_be_updated(conversation_id, user_id)
        
        # 验证dataset和workspace权限
        await chat_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        if tenant_id and quota_service:
            try:
                await quota_service.check_and_increment(str(tenant_id), "chat_messages_monthly", 1)
            except QuotaExceededError:
                raise
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(
                    "chat_messages_monthly 配额计数失败，已跳过本次计数: tenant=%s error=%s",
                    tenant_id,
                    e,
                    exc_info=True,
                )
        
        result = await chat_service.chat(
            dataset_id=dataset_id,
            query=request.query,
            conversation_id=conversation_id,
            history=[msg.model_dump() for msg in request.history] if request.history else None,
            retrieval_mode=request.retrieval_mode.value,
            top_k=request.top_k,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        return {"success": True, "data": result}
    except QuotaExceededError:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.error("Failed to process chat: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process chat")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    quota_service: Annotated[Any, Depends(get_quota_service)],
):
    """流式对话请求"""
    try:
        import json
        
        dataset_id = UUID(request.dataset_id)
        conversation_id = UUID(request.conversation_id) if request.conversation_id else None
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")

        await _assert_conversation_can_be_updated(conversation_id, user_id)
        
        # 验证dataset和workspace权限
        await chat_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        if tenant_id and quota_service:
            try:
                await quota_service.check_and_increment(str(tenant_id), "chat_messages_monthly", 1)
            except QuotaExceededError:
                raise
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(
                    "chat_messages_monthly 配额计数失败，已跳过本次计数: tenant=%s error=%s",
                    tenant_id,
                    e,
                    exc_info=True,
                )

        async def generate():
            async for chunk in chat_service.chat_stream(
                dataset_id=dataset_id,
                query=request.query,
                conversation_id=conversation_id,
                history=[msg.model_dump() for msg in request.history] if request.history else None,
                retrieval_mode=request.retrieval_mode.value,
                top_k=request.top_k,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                user_id=user_id,
                tenant_id=tenant_id,
            ):
                # 使用 json.dumps 确保输出标准的 JSON 格式（双引号）
                yield f"data: {json.dumps(chunk)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"}
        )
    except QuotaExceededError:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.error("Failed to process chat stream: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process chat stream")


@router.post("/async")
async def chat_async_submit(
    request: Request,
    body: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    quota_service: Annotated[Any, Depends(get_quota_service)],
):
    """提交聊天异步任务，立即返回 job_id。"""
    try:
        dataset_id = UUID(body.dataset_id)
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")
        conversation_id = UUID(body.conversation_id) if body.conversation_id else None

        await _assert_conversation_can_be_updated(conversation_id, user_id)

        await chat_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        if tenant_id and quota_service:
            await quota_service.check_and_increment(str(tenant_id), "chat_messages_monthly", 1)

        payload = {
            "dataset_id": str(dataset_id),
            "query": body.query,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "history": [msg.model_dump() for msg in body.history] if body.history else None,
            "retrieval_mode": body.retrieval_mode.value,
            "top_k": body.top_k,
            "temperature": body.temperature,
            "max_tokens": body.max_tokens,
            "user_id": user_id,
            "tenant_id": str(tenant_id) if tenant_id else "",
        }

        async_result = process_chat_async_task.apply_async(args=[payload], queue="chat_async")
        await _bind_chat_job_owner(request, async_result.id, user_id, str(tenant_id) if tenant_id else None)

        return {
            "success": True,
            "data": {
                "job_id": async_result.id,
                "status": "PENDING",
            },
        }
    except QuotaExceededError:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.error("Failed to submit async chat job: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit chat job")


@router.get("/jobs/{job_id}")
async def chat_async_job_status(
    request: Request,
    job_id: str,
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """查询聊天异步任务状态。"""
    await _assert_chat_job_owner(request, job_id, current_user["sub"])

    result = AsyncResult(job_id, app=celery_app)
    state = str(result.state or "PENDING").upper()
    if state in {"PENDING", "STARTED", "RETRY"}:
        return {"success": True, "data": {"job_id": job_id, "status": state}}
    if state == "SUCCESS":
        payload = result.result if isinstance(result.result, dict) else {"raw": result.result}
        return {
            "success": True,
            "data": {
                "job_id": job_id,
                "status": "SUCCESS",
                "result": payload,
            },
        }
    return {
        "success": True,
        "data": {
            "job_id": job_id,
            "status": "FAILURE",
            "error": str(result.result),
        },
    }


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreateRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """创建会话（支持可见性设置）"""
    try:
        dataset_id = UUID(request.dataset_id)
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")
        
        # 验证dataset和workspace权限
        await chat_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        # 转换visibility枚举
        visibility_value = request.visibility.value if request.visibility else "private"
        
        result = await chat_service.create_conversation(
            dataset_id=dataset_id,
            user_id=user_id,
            title=request.title,
            metadata=request.metadata,
            visibility=visibility_value,
            workspace_id=UUID(request.workspace_id) if request.workspace_id else None
        )
        return {"success": True, "message": "Conversation created successfully", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to create conversation: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create conversation")


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """获取会话详情（支持权限检查）"""
    from infrastructure.database.session import AsyncSessionLocal
    
    user_id = current_user["sub"]
    
    # 使用权限检查器验证访问权限
    async with AsyncSessionLocal() as session:
        has_permission = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=session
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    
    result = await chat_service.get_conversation(conversation_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    
    return {"success": True, "data": result}


@router.put("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: UUID,
    request: ConversationUpdateRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """更新会话（支持可见性变更和权限检查）"""
    try:
        from infrastructure.database.session import AsyncSessionLocal
        
        user_id = current_user["sub"]
        
        # 使用权限检查器验证修改权限
        async with AsyncSessionLocal() as session:
            has_permission = await permission_checker.check_conversation_access(
                user_id=user_id,
                conversation_id=conversation_id,
                action=PermissionAction.UPDATE,
                session=session
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        
        update_data = request.model_dump(exclude_unset=True)
        
        # 转换visibility枚举
        if 'visibility' in update_data and update_data['visibility']:
            update_data['visibility'] = update_data['visibility'].value
        
        result = await chat_service.update_conversation(conversation_id, **update_data)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update conversation %s: %s", conversation_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update conversation")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """删除会话（支持权限检查）"""
    from infrastructure.database.session import AsyncSessionLocal
    
    user_id = current_user["sub"]
    
    # 使用权限检查器验证删除权限
    async with AsyncSessionLocal() as session:
        has_permission = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.DELETE,
            session=session
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    
    success = await chat_service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"success": True, "message": "Conversation deleted successfully"}


@router.get("/conversations")
async def list_conversations(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    dataset_id: str = None,
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """查询会话列表"""
    from core.value_objects.pagination import Pagination
    from uuid import UUID
    
    user_id = current_user["sub"]
    
    # 使用 chat_service 来获取会话列表
    pagination = Pagination(page=page, page_size=page_size)
    
    result = await chat_service.list_conversations(
        user_id=user_id,
        dataset_id=UUID(dataset_id) if dataset_id else None,
        keyword=keyword,
        pagination=pagination
    )
    
    total_pages = (result.total + result.page_size - 1) // result.page_size if result.page_size > 0 else 0
    
    return {
        "success": True,
        "data": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": total_pages,
        "has_next": result.page < total_pages,
        "has_prev": result.page > 1
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """获取会话消息历史（支持权限检查）"""
    from infrastructure.database.session import AsyncSessionLocal
    
    user_id = current_user["sub"]
    
    # 使用权限检查器验证访问权限
    async with AsyncSessionLocal() as session:
        has_permission = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=session
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    
    result = await chat_service.get_conversation_messages(conversation_id)
    return {"success": True, "data": result}


@router.get("/admin/conversations")
async def admin_list_conversations(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    request: AdminConversationQueryRequest = Depends()
):
    """
    管理员查询会话列表（支持高级过滤）
    
    权限要求：租户管理员或超级管理员
    支持按用户、工作空间、可见性、日期范围等条件过滤
    """
    from infrastructure.database.session import AsyncSessionLocal
    
    user_id = current_user["sub"]
    
    # 验证用户是否为管理员（租户管理员或超级管理员）
    async with AsyncSessionLocal() as session:
        role_info = await permission_checker.get_user_role_info(user_id, session)
        
        if not (role_info.get("is_superuser") or role_info.get("is_tenant_admin")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        # 构建过滤条件
        filters = {}
        
        if request.user_id:
            filters["user_id"] = request.user_id
        
        if request.workspace_id:
            filters["workspace_id"] = request.workspace_id
        
        if request.visibility:
            filters["visibility"] = request.visibility.value
        
        if request.dataset_id:
            filters["dataset_id"] = request.dataset_id
        
        if request.keyword:
            filters["keyword"] = request.keyword
        
        # 创建分页对象
        from core.value_objects.pagination import Pagination
        pagination = Pagination(page=request.page, page_size=request.page_size)
        
        try:
            result = await chat_service.list_conversations_with_permissions(
                user_id=user_id,
                filters=filters if filters else None,
                pagination=pagination
            )
            
            return {
                "success": True,
                "data": result.items,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "total_pages": (result.total + result.page_size - 1) // result.page_size if result.page_size > 0 else 0,
                "has_next": result.page < ((result.total + result.page_size - 1) // result.page_size) if result.page_size > 0 else False,
                "has_prev": result.page > 1
            }
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.exception("Admin conversation query failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to query conversations"
            )
