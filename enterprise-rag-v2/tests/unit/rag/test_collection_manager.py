"""
CollectionManager单元测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.rag.collection_manager import CollectionManager, CollectionManagerFactory


class TestCollectionManager:
    """CollectionManager测试"""

    @pytest.fixture
    def mock_vector_store(self):
        """模拟向量存储"""
        store = AsyncMock()
        store.collection_exists = AsyncMock(return_value=True)
        store.create_collection = AsyncMock(return_value=True)
        return store

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_already_exists(self, mock_vector_store):
        """测试集合已存在的情况"""
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        result = await manager.ensure_collection_exists()
        
        assert result is True
        mock_vector_store.collection_exists.assert_called_once()
        mock_vector_store.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_creates_new(self, mock_vector_store):
        """测试创建新集合"""
        mock_vector_store.collection_exists = AsyncMock(return_value=False)
        
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        result = await manager.ensure_collection_exists()
        
        assert result is True
        mock_vector_store.collection_exists.assert_called_once()
        mock_vector_store.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_collection_info_exists(self, mock_vector_store):
        """测试获取已存在集合的信息"""
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        info = await manager.get_collection_info()
        
        assert info["exists"] is True
        assert info["name"] == "test_collection"
        assert info["status"] == "ready"

    @pytest.mark.asyncio
    async def test_get_collection_info_not_exists(self, mock_vector_store):
        """测试获取不存在集合的信息"""
        mock_vector_store.collection_exists = AsyncMock(return_value=False)
        
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        info = await manager.get_collection_info()
        
        assert info["exists"] is False
        assert info["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_diagnose(self, mock_vector_store):
        """测试诊断功能"""
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        result = await manager.diagnose()
        
        assert "collection_name" in result
        assert "checks" in result
        assert "overall_status" in result
        assert len(result["checks"]) == 3

    def test_get_workspace_collection_name(self):
        """测试获取工作空间集合名称"""
        workspace_id = "12345678-1234-1234-1234-123456789012"
        
        name = CollectionManager.get_workspace_collection_name(workspace_id)
        
        assert "test" in name or workspace_id.replace("-", "_") in name


class TestCollectionManagerFactory:
    """CollectionManagerFactory测试"""

    def test_create_default(self):
        """测试创建默认管理器"""
        manager = CollectionManagerFactory.create()
        
        assert manager is not None
        assert manager.collection_name is not None

    def test_create_with_name(self):
        """测试创建指定名称的管理器"""
        manager = CollectionManagerFactory.create(
            collection_name="custom_collection"
        )
        
        assert manager.collection_name == "custom_collection"

    def test_create_memory_store(self):
        """测试创建内存存储管理器"""
        manager = CollectionManagerFactory.create(use_memory=True)
        
        assert manager is not None
        assert manager._vector_store is not None
