"""
缓存抽象接口

定义缓存服务的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
from datetime import timedelta


class CacheProvider(ABC):
    """缓存提供商抽象接口"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> bool:
        """设置缓存值"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        pass
    
    @abstractmethod
    async def expire(self, key: str, ttl: timedelta) -> bool:
        """设置缓存过期时间"""
        pass
    
    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        pass
    
    @abstractmethod
    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[timedelta] = None) -> bool:
        """批量设置缓存"""
        pass
    
    @abstractmethod
    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存"""
        pass
    
    @abstractmethod
    async def clear_pattern(self, pattern: str) -> int:
        """根据模式清除缓存"""
        pass