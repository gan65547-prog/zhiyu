"""
向量集合管理器

提供向量数据库集合的统一管理，确保集合正确创建和配置
支持多工作空间隔离
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import httpx

from core.rag.vector_store import VectorStore, QdrantVectorStore, MemoryVectorStore
from core.rag_config import get_rag_config
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class CollectionManager:
    """
    向量集合管理器
    
    职责：
    1. 确保集合存在
    2. 管理集合配置
    3. 提供集合诊断
    4. 支持多工作空间隔离
    """
    
    DEFAULT_VECTOR_SIZE = 1536
    DEFAULT_DISTANCE = "Cosine"
    
    _instances: Dict[str, 'CollectionManager'] = {}
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        collection_name: Optional[str] = None,
        vector_store: Optional[VectorStore] = None
    ):
        self.config = get_rag_config()
        self.collection_name = collection_name or self.config.collection_name
        self._vector_store = vector_store
        self._initialized = False
    
    @classmethod
    async def get_instance(
        cls,
        collection_name: Optional[str] = None
    ) -> 'CollectionManager':
        """获取单例实例"""
        name = collection_name or get_rag_config().collection_name
        
        async with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = CollectionManager(collection_name=name)
            return cls._instances[name]
    
    @property
    def vector_store(self) -> VectorStore:
        """获取向量存储实例"""
        if self._vector_store is None:
            self._vector_store = QdrantVectorStore(
                collection_name=self.collection_name
            )
        return self._vector_store
    
    async def ensure_collection_exists(
        self,
        vector_size: Optional[int] = None
    ) -> bool:
        """
        确保集合存在，不存在则创建
        
        Args:
            vector_size: 向量维度，默认使用配置值
            
        Returns:
            bool: 操作是否成功
        """
        try:
            exists = await self.vector_store.collection_exists()
            
            if exists:
                logger.info(f"Collection '{self.collection_name}' already exists")
                self._initialized = True
                return True
            
            size = vector_size or self.DEFAULT_VECTOR_SIZE
            success = await self.vector_store.create_collection(vector_size=size)
            
            if success:
                logger.info(f"Created collection '{self.collection_name}' with vector size {size}")
                self._initialized = True
            else:
                logger.error(f"Failed to create collection '{self.collection_name}'")
            
            return success
            
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.exception("Error ensuring collection exists: %s", e)
            return False
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息
        
        Returns:
            Dict: 集合信息
        """
        try:
            exists = await self.vector_store.collection_exists()
            
            if not exists:
                return {
                    "exists": False,
                    "name": self.collection_name,
                    "status": "not_found"
                }
            
            return {
                "exists": True,
                "name": self.collection_name,
                "status": "ready",
                "vector_size": self.DEFAULT_VECTOR_SIZE,
                "distance": self.DEFAULT_DISTANCE
            }
            
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.exception("Error getting collection info: %s", e)
            return {
                "exists": False,
                "name": self.collection_name,
                "status": "error",
                "error": str(e)
            }
    
    async def diagnose(self) -> Dict[str, Any]:
        """
        诊断集合状态
        
        Returns:
            Dict: 诊断结果
        """
        results = {
            "collection_name": self.collection_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": []
        }
        
        checks = [
            ("vector_db_connection", self._check_vector_db_connection),
            ("collection_exists", self._check_collection_exists),
            ("collection_config", self._check_collection_config)
        ]
        
        for check_name, check_func in checks:
            try:
                check_result = await check_func()
                results["checks"].append({
                    "name": check_name,
                    "status": "passed" if check_result.get("success") else "failed",
                    "details": check_result
                })
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning("Collection diagnostic check failed: %s error=%s", check_name, e, exc_info=True)
                results["checks"].append({
                    "name": check_name,
                    "status": "error",
                    "details": {"error": str(e)}
                })
        
        overall_status = all(
            c["status"] == "passed" for c in results["checks"]
        )
        results["overall_status"] = "healthy" if overall_status else "unhealthy"
        
        return results
    
    async def _check_vector_db_connection(self) -> Dict[str, Any]:
        """检查向量数据库连接"""
        try:
            config = get_rag_config()
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{config.qdrant_url}/collections")
                
                if response.status_code == 200:
                    return {"success": True, "message": "Vector DB connection OK"}
                else:
                    return {
                        "success": False,
                        "message": f"Vector DB returned status {response.status_code}"
                    }
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {"success": False, "message": f"Connection failed: {str(e)}"}
    
    async def _check_collection_exists(self) -> Dict[str, Any]:
        """检查集合是否存在"""
        try:
            exists = await self.vector_store.collection_exists()
            return {
                "success": exists,
                "message": f"Collection {'exists' if exists else 'not found'}"
            }
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {"success": False, "message": str(e)}
    
    async def _check_collection_config(self) -> Dict[str, Any]:
        """检查集合配置"""
        try:
            info = await self.get_collection_info()
            if info.get("exists"):
                return {
                    "success": True,
                    "message": "Collection config valid",
                    "config": info
                }
            return {"success": False, "message": "Collection not found"}
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def get_workspace_collection_name(workspace_id: str) -> str:
        """
        获取工作空间对应的集合名称
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            str: 集合名称
        """
        config = get_rag_config()
        return f"{config.collection_name}_{workspace_id.replace('-', '_')}"
    
    @staticmethod
    async def ensure_workspace_collection(
        workspace_id: str,
        vector_size: Optional[int] = None
    ) -> bool:
        """
        确保工作空间集合存在
        
        Args:
            workspace_id: 工作空间ID
            vector_size: 向量维度
            
        Returns:
            bool: 操作是否成功
        """
        collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
        manager = await CollectionManager.get_instance(collection_name)
        return await manager.ensure_collection_exists(vector_size)


class CollectionManagerFactory:
    """集合管理器工厂"""
    
    @staticmethod
    def create(
        collection_name: Optional[str] = None,
        use_memory: bool = False
    ) -> CollectionManager:
        """
        创建集合管理器
        
        Args:
            collection_name: 集合名称
            use_memory: 是否使用内存存储（用于测试）
            
        Returns:
            CollectionManager: 集合管理器实例
        """
        if use_memory:
            vector_store = MemoryVectorStore(collection_name=collection_name)
            return CollectionManager(
                collection_name=collection_name,
                vector_store=vector_store
            )
        
        return CollectionManager(collection_name=collection_name)
