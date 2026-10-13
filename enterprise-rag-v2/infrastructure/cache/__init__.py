"""
Cache package
"""

from infrastructure.cache.redis import RedisCache, CacheKeys, get_cache, close_cache

__all__ = [
    "RedisCache",
    "CacheKeys",
    "get_cache",
    "close_cache",
    "get_redis",
]

async def get_redis():
    """获取Redis客户端"""
    cache = await get_cache()
    return await cache._get_client()
