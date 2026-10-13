"""
缓存服务

提供内存缓存和Redis缓存支持，用于提高系统性能
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, List, Generic, TypeVar
from datetime import datetime
from abc import ABC, abstractmethod
from collections import OrderedDict
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CacheBackend(ABC, Generic[T]):
    """缓存后端抽象类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[T]:
        """获取缓存值"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """清空缓存"""
        pass


class MemoryCacheBackend(CacheBackend[T]):
    """内存缓存后端"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                del self._cache[key]
                return None
            
            self._cache.move_to_end(key)
            return entry["value"]
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        async with self._lock:
            expires_at = time.time() + ttl if ttl else None
            
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time()
            }
            
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
            
            return True
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        async with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                del self._cache[key]
                return False
            
            return True
    
    async def clear(self) -> bool:
        async with self._lock:
            self._cache.clear()
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "memory_usage": sum(
                len(str(entry)) for entry in self._cache.values()
            )
        }


class RedisCacheBackend(CacheBackend[T]):
    """Redis缓存后端"""
    
    def __init__(self, redis_client, prefix: str = "cache:"):
        self._redis = redis_client
        self._prefix = prefix
    
    def _get_key(self, key: str) -> str:
        return f"{self._prefix}{key}"
    
    async def get(self, key: str) -> Optional[T]:
        try:
            value = await self._redis.get(self._get_key(key))
            if value is None:
                return None
            return json.loads(value)
        except (RuntimeError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        try:
            serialized = json.dumps(value)
            if ttl:
                await self._redis.setex(self._get_key(key), ttl, serialized)
            else:
                await self._redis.set(self._get_key(key), serialized)
            return True
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        try:
            await self._redis.delete(self._get_key(key))
            return True
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        try:
            return await self._redis.exists(self._get_key(key)) > 0
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> bool:
        try:
            keys = await self._redis.keys(f"{self._prefix}*")
            if keys:
                await self._redis.delete(*keys)
            return True
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Redis clear error: {e}")
            return False


class CacheService:
    """缓存服务"""
    
    _instance: Optional['CacheService'] = None
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        self._backend = backend or MemoryCacheBackend()
        self._hit_count = 0
        self._miss_count = 0
    
    @classmethod
    def get_instance(cls) -> 'CacheService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def get(self, key: str) -> Optional[Any]:
        value = await self._backend.get(key)
        
        if value is not None:
            self._hit_count += 1
            logger.debug(f"Cache hit: {key}")
        else:
            self._miss_count += 1
            logger.debug(f"Cache miss: {key}")
        
        return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return await self._backend.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)
    
    async def exists(self, key: str) -> bool:
        return await self._backend.exists(key)
    
    async def clear(self) -> bool:
        return await self._backend.clear()
    
    async def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: Optional[int] = None
    ) -> Any:
        value = await self.get(key)
        
        if value is not None:
            return value
        
        value = await factory()
        await self.set(key, value, ttl)
        
        return value
    
    def get_stats(self) -> Dict[str, Any]:
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        
        stats = {
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "total_requests": total,
            "hit_rate": hit_rate
        }
        
        if isinstance(self._backend, MemoryCacheBackend):
            stats.update(self._backend.get_stats())
        
        return stats
    
    def reset_stats(self) -> None:
        self._hit_count = 0
        self._miss_count = 0


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存过期时间（秒）
        key_prefix: 缓存键前缀
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache = CacheService.get_instance()
            
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            return await cache.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl
            )
        
        return wrapper
    return decorator


class EmbeddingCache:
    """嵌入向量缓存"""
    
    def __init__(self, cache_service: CacheService):
        self._cache = cache_service
        self._prefix = "embedding:"
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        key = f"{self._prefix}{hash(text)}"
        return await self._cache.get(key)
    
    async def set_embedding(self, text: str, embedding: List[float], ttl: int = 3600) -> bool:
        key = f"{self._prefix}{hash(text)}"
        return await self._cache.set(key, embedding, ttl)


class QueryResultCache:
    """查询结果缓存"""
    
    def __init__(self, cache_service: CacheService):
        self._cache = cache_service
        self._prefix = "query:"
    
    async def get_results(self, query: str, dataset_id: str) -> Optional[List[Dict]]:
        key = f"{self._prefix}{dataset_id}:{hash(query)}"
        return await self._cache.get(key)
    
    async def set_results(
        self,
        query: str,
        dataset_id: str,
        results: List[Dict],
        ttl: int = 600
    ) -> bool:
        key = f"{self._prefix}{dataset_id}:{hash(query)}"
        return await self._cache.set(key, results, ttl)
    
    async def invalidate_dataset(self, dataset_id: str) -> bool:
        return await self._cache.delete(f"{self._prefix}{dataset_id}:*")
