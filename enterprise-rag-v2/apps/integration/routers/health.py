"""
健康检查路由

监控消息网关的健康状态
"""

from fastapi import APIRouter, Request
from datetime import datetime

from apps.integration.monitoring.metrics import MetricsService
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Integration"])


@router.get("")
async def health_check(request: Request):
    """
    健康检查端点
    
    Returns:
        健康状态信息
    """
    try:
        # 检查数据库连接
        db = getattr(request.app.state, 'db', None)
        db_status = "ok" if db else "unavailable"
        
        # 检查Redis连接
        redis = getattr(request.app.state, 'redis', None) or (
            # 尝试从cache模块获取
            __import__('infrastructure.cache', fromlist=['get_redis'])
            .get_redis()
        )
        redis_status = "ok" if redis else "unavailable"
        
        # 检查配额服务
        quota_service = getattr(request.app.state, 'quota_service', None)
        quota_status = "ok" if quota_service else "unavailable"
        
        # 构建健康状态
        health_status = {
            "status": "healthy" if all([db, redis]) else "degraded",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "database": db_status,
                "redis": redis_status,
                "quota_service": quota_status
            },
            "version": "1.0.0"
        }
        
        logger.debug(f"[Health] 健康检查: {health_status['status']}")
        
        return health_status
        
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.error(f"[Health] 健康检查失败: {e}", exc_info=True)
        
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/metrics")
async def get_metrics():
    """
    获取监控指标
    
    Returns:
        Prometheus格式的监控指标
    """
    try:
        metrics = MetricsService.get_metrics()
        return metrics
        
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.error(f"[Metrics] 获取指标失败: {e}", exc_info=True)
        
        return {
            "error": "Failed to get metrics"
        }
