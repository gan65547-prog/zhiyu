"""
用户绑定路由

处理平台用户与系统用户的绑定关系
"""

import json
from fastapi import APIRouter, Request, HTTPException, Depends

from apps.integration.services.user_mapping import UserMappingService
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/bind", tags=["Integration"])


def get_user_mapping_service(request: Request) -> UserMappingService:
    """依赖注入: 获取UserMappingService实例"""
    
    db = getattr(request.app.state, 'db', None)
    redis = getattr(request.app.state, 'redis', None) or (
        # 尝试从cache模块获取
        __import__('infrastructure.cache', fromlist=['get_redis'])
        .get_redis()
    )
    quota_svc = getattr(request.app.state, 'quota_service', None)
    
    return UserMappingService(
        db=db,
        redis=redis,
        quota_service=quota_svc
    )


@router.post("/verify")
async def verify_bind_code(
    request: Request,
    bind_code: str,
    user_id: int,
    user_mapping_service: UserMappingService = Depends(get_user_mapping_service),
):
    """
    验证绑定码并关联用户
    
    Args:
        bind_code: 绑定码
        user_id: 系统用户ID
        
    Returns:
        绑定结果
    """
    if not bind_code or not user_id:
        raise HTTPException(
            status_code=400,
            detail="缺少必要参数: bind_code, user_id"
        )
    
    logger.info(
        f"[Bind] 验证绑定码",
        extra={
            "bind_code": bind_code,
            "user_id": user_id
        }
    )
    
    try:
        # 从Redis获取绑定码信息
        redis = user_mapping_service.redis
        if not redis:
            raise HTTPException(
                status_code=500,
                detail="Redis未初始化，无法验证绑定码"
            )
        
        cache_key = f"integration:bind:{bind_code}"
        cached_data = await redis.get(cache_key)
        
        if not cached_data:
            raise HTTPException(
                status_code=400,
                detail="绑定码无效或已过期"
            )
        
        # 解析缓存数据
        bind_info = json.loads(cached_data)
        platform = bind_info.get("platform")
        platform_user_id = bind_info.get("platform_user_id")
        user_info = bind_info.get("user_info", {})
        
        if not platform or not platform_user_id:
            raise HTTPException(
                status_code=400,
                detail="绑定码信息不完整"
            )
        
        # 检查系统用户是否存在
        db = user_mapping_service.db
        if not db:
            raise HTTPException(
                status_code=500,
                detail="数据库未初始化"
            )
        
        # 检查用户是否存在
        user_query = """
            SELECT id, tenant_id FROM users WHERE id = :user_id
        """
        user_result = await db.fetch_one(user_query, {"user_id": user_id})
        
        if not user_result:
            raise HTTPException(
                status_code=404,
                detail="系统用户不存在"
            )
        
        tenant_id = user_result["tenant_id"]
        
        # 检查是否已存在映射
        existing_query = """
            SELECT id FROM platform_users 
            WHERE platform = :platform AND platform_user_id = :platform_user_id
        """
        existing_result = await db.fetch_one(existing_query, {
            "platform": platform,
            "platform_user_id": platform_user_id
        })
        
        if existing_result:
            raise HTTPException(
                status_code=400,
                detail="该平台用户已绑定"
            )
        
        # 创建平台映射
        mapping_query = """
            INSERT INTO platform_users (
                platform, platform_user_id, system_user_id, tenant_id,
                display_name, avatar_url, email, metadata
            ) VALUES (
                :platform, :platform_user_id, :system_user_id, :tenant_id,
                :display_name, :avatar_url, :email, :metadata::jsonb
            )
        """
        await db.execute(mapping_query, {
            "platform": platform,
            "platform_user_id": platform_user_id,
            "system_user_id": user_id,
            "tenant_id": tenant_id,
            "display_name": user_info.get("name", platform_user_id),
            "avatar_url": user_info.get("avatar_url"),
            "email": user_info.get("email"),
            "metadata": user_info or {}
        })
        
        # 删除绑定码
        await redis.delete(cache_key)
        
        logger.info(
            f"[Bind] 绑定成功",
            extra={
                "platform": platform,
                "platform_user_id": platform_user_id,
                "system_user_id": user_id
            }
        )
        
        return {
            "success": True,
            "message": "绑定成功",
            "data": {
                "platform": platform,
                "platform_user_id": platform_user_id,
                "system_user_id": user_id
            }
        }
        
    except HTTPException:
        raise
    
    except (json.JSONDecodeError, RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"[Bind] 验证绑定码失败",
            extra={
                "bind_code": bind_code,
                "user_id": user_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail="验证绑定码时发生错误"
        )


@router.get("/status")
async def get_bind_status(
    request: Request,
    platform: str,
    platform_user_id: str,
    user_mapping_service: UserMappingService = Depends(get_user_mapping_service),
):
    """
    获取绑定状态
    
    Args:
        platform: 平台
        platform_user_id: 平台用户ID
        
    Returns:
        绑定状态
    """
    if not platform or not platform_user_id:
        raise HTTPException(
            status_code=400,
            detail="缺少必要参数: platform, platform_user_id"
        )
    
    logger.info(
        f"[Bind] 查询绑定状态",
        extra={
            "platform": platform,
            "platform_user_id": platform_user_id
        }
    )
    
    try:
        # 查询映射
        mapping = await user_mapping_service._query_existing_mapping(
            platform, platform_user_id
        )
        
        if mapping:
            return {
                "success": True,
                "bound": True,
                "data": {
                    "system_user_id": mapping["system_user_id"],
                    "tenant_id": mapping["tenant_id"],
                    "display_name": mapping["display_name"],
                    "created_at": mapping["created_at"].isoformat()
                }
            }
        else:
            return {
                "success": True,
                "bound": False,
                "message": "未绑定"
            }
            
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.error(
            f"[Bind] 查询绑定状态失败",
            extra={
                "platform": platform,
                "platform_user_id": platform_user_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail="查询绑定状态时发生错误"
        )
