"""
Redis缓存实现

提供Redis缓存接口的实现
"""

from typing import Optional, Any, List
import json
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import RedisError

from core.config import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Redis缓存服务"""

    def __init__(self, url: Optional[str] = None):
        self.settings = get_settings()
        self.url = url or self.settings.redis.url
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def _get_pool(self) -> ConnectionPool:
        """获取连接池"""
        if self._pool is None:
            self._pool = ConnectionPool.from_url(
                self.url,
                max_connections=self.settings.redis.pool_size,
                decode_responses=True
            )
        return self._pool

    async def _get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self._client is None:
            pool = await self._get_pool()
            self._client = redis.Redis(connection_pool=pool)
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value is None:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis get failed: key=%s error=%s", key, exc, exc_info=True)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值"""
        try:
            client = await self._get_client()

            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)

            if ttl:
                await client.setex(key, ttl, value)
            else:
                await client.set(key, value)
            return True
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis set failed: key=%s error=%s", key, exc, exc_info=True)
            return False

    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        """兼容 redis-py setex 接口。"""
        return await self.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis delete failed: key=%s error=%s", key, exc, exc_info=True)
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            client = await self._get_client()
            return await client.exists(key) > 0
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis exists failed: key=%s error=%s", key, exc, exc_info=True)
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        try:
            client = await self._get_client()
            return await client.expire(key, ttl)
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis expire failed: key=%s error=%s", key, exc, exc_info=True)
            return False

    async def hget(self, key: str, field: str) -> Optional[str]:
        """获取 Hash 字段值。"""
        try:
            client = await self._get_client()
            return await client.hget(key, field)
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis hget failed: key=%s field=%s error=%s", key, field, exc, exc_info=True)
            return None

    async def hset(self, key: str, field: str, value: Any) -> int:
        """设置 Hash 字段值。"""
        try:
            client = await self._get_client()
            return await client.hset(key, field, value)
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis hset failed: key=%s field=%s error=%s", key, field, exc, exc_info=True)
            return 0

    async def hgetall(self, key: str) -> dict:
        """获取 Hash 全字段。"""
        try:
            client = await self._get_client()
            return await client.hgetall(key)
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis hgetall failed: key=%s error=%s", key, exc, exc_info=True)
            return {}

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """原子递增 Hash 字段。"""
        client = await self._get_client()
        return await client.hincrby(key, field, amount)

    async def pipeline(self):
        """暴露 pipeline 以兼容现有调用。"""
        client = await self._get_client()
        return client.pipeline()

    async def ttl(self, key: str) -> int:
        """获取剩余生存时间"""
        try:
            client = await self._get_client()
            return await client.ttl(key)
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis ttl failed: key=%s error=%s", key, exc, exc_info=True)
            return -1

    async def get_many(self, keys: List[str]) -> dict:
        """批量获取"""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(
        self,
        mapping: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """批量设置"""
        try:
            client = await self._get_client()
            pipe = client.pipeline()
            for key, value in mapping.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                if ttl:
                    pipe.setex(key, ttl, value)
                else:
                    pipe.set(key, value)
            await pipe.execute()
            return True
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis set_many failed: keys=%s error=%s", list(mapping.keys()), exc, exc_info=True)
            return False

    async def delete_many(self, keys: List[str]) -> int:
        """批量删除"""
        try:
            client = await self._get_client()
            result = await client.delete(*keys)
            return result
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis delete_many failed: keys=%s error=%s", keys, exc, exc_info=True)
            return 0

    async def clear_pattern(self, pattern: str) -> int:
        """删除匹配模式的所有键"""
        try:
            client = await self._get_client()
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await client.delete(*keys)
            return 0
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Redis clear_pattern failed: pattern=%s error=%s", pattern, exc, exc_info=True)
            return 0

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None


class CacheKeys:
    """缓存键生成工具"""

    @staticmethod
    def user(user_id: str) -> str:
        """用户缓存键"""
        return f"user:{user_id}"

    @staticmethod
    def user_session(user_id: str) -> str:
        """用户会话缓存键"""
        return f"session:user:{user_id}"

    @staticmethod
    def tenant(tenant_id: str) -> str:
        """租户缓存键"""
        return f"tenant:{tenant_id}"

    @staticmethod
    def workspace(workspace_id: str) -> str:
        """工作空间缓存键"""
        return f"workspace:{workspace_id}"

    @staticmethod
    def dataset(dataset_id: str) -> str:
        """数据集缓存键"""
        return f"dataset:{dataset_id}"

    @staticmethod
    def document(document_id: str) -> str:
        """文档缓存键"""
        return f"document:{document_id}"

    @staticmethod
    def dataset_list(workspace_id: str) -> str:
        """数据集列表缓存键"""
        return f"dataset_list:{workspace_id}"

    @staticmethod
    def document_list(dataset_id: str) -> str:
        """文档列表缓存键"""
        return f"document_list:{dataset_id}"

    @staticmethod
    def conversation(conversation_id: str) -> str:
        """会话缓存键"""
        return f"conversation:{conversation_id}"

    @staticmethod
    def embedding(text_hash: str) -> str:
        """Embedding缓存键"""
        return f"embedding:{text_hash}"

    @staticmethod
    def api_response(endpoint: str, params_hash: str) -> str:
        """API响应缓存键"""
        return f"api:{endpoint}:{params_hash}"


_cache_instance: Optional[RedisCache] = None


async def get_cache() -> RedisCache:
    """获取缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


async def close_cache() -> None:
    """关闭缓存连接"""
    global _cache_instance
    if _cache_instance:
        await _cache_instance.close()
        _cache_instance = None
