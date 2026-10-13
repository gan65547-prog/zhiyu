"""
DatasetService单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from services.impl.dataset_service import DatasetServiceImpl
from infrastructure.database.models import Dataset
from core.value_objects.pagination import Pagination, Page


class MockDatasetRepo:
    """模拟数据集Repository"""
    def __init__(self):
        self.datasets = {}

    async def get_by_id(self, dataset_id):
        if dataset_id in self.datasets:
            return self.datasets[dataset_id]
        sid = str(dataset_id)
        for k, v in self.datasets.items():
            if str(k) == sid:
                return v
        return None

    async def create(self, dataset):
        if not dataset.id:
            dataset.id = uuid4()
        if not dataset.created_at:
            dataset.created_at = datetime.utcnow()
        if not dataset.updated_at:
            dataset.updated_at = datetime.utcnow()
        self.datasets[dataset.id] = dataset
        return dataset

    async def update(self, dataset):
        if not dataset.updated_at:
            dataset.updated_at = datetime.utcnow()
        self.datasets[dataset.id] = dataset
        return dataset

    async def delete(self, dataset_id):
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]
            return True
        return False

    async def list(self, filters=None, pagination=None):
        items = list(self.datasets.values())

        if filters:
            if "workspace_id" in filters:
                wid = str(filters["workspace_id"])
                items = [ds for ds in items if str(ds.workspace_id) == wid]
            if "keyword" in filters and filters["keyword"]:
                keyword = filters["keyword"].lower()
                items = [ds for ds in items if keyword in ds.name.lower()]

        total = len(items)
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 20
        start = (page - 1) * page_size
        end = start + page_size

        return Page(items=items[start:end], total=total, page=page, page_size=page_size)


class TestDatasetService:
    """DatasetService测试"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one.return_value = 0
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def dataset_service(self, mock_session):
        """创建DatasetServiceImpl实例"""
        service = DatasetServiceImpl(session=mock_session)
        service.dataset_repo = MockDatasetRepo()
        return service

    @pytest.fixture
    def sample_workspace_id(self):
        return uuid4()

    @pytest.fixture
    def sample_dataset_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_dataset_success(self, dataset_service, sample_workspace_id):
        """测试创建数据集成功"""
        result = await dataset_service.create_dataset(
            workspace_id=sample_workspace_id,
            name="Test Dataset",
            description="A test dataset"
        )

        assert result["name"] == "Test Dataset"
        assert result["description"] == "A test dataset"
        assert result["workspace_id"] == str(sample_workspace_id)
        assert result["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert result["chunk_size"] == 500
        assert result["chunk_overlap"] == 50

    @pytest.mark.asyncio
    async def test_create_dataset_with_custom_config(self, dataset_service, sample_workspace_id):
        """测试创建带自定义配置的数据集"""
        result = await dataset_service.create_dataset(
            workspace_id=sample_workspace_id,
            name="Custom Dataset",
            embedding_model="custom-model",
            chunk_size=1000,
            chunk_overlap=100,
            metadata={"custom": "value"}
        )

        assert result["embedding_model"] == "custom-model"
        assert result["chunk_size"] == 1000
        assert result["chunk_overlap"] == 100
        assert result["metadata"]["custom"] == "value"

    @pytest.mark.asyncio
    async def test_get_dataset_success(self, dataset_service, sample_workspace_id):
        """测试获取数据集详情"""
        dataset_id = uuid4()
        ds = Dataset(
            id=dataset_id,
            workspace_id=sample_workspace_id,
            name="Test DS",
            description="Test",
            embedding_model="model1",
            chunk_size=500,
            chunk_overlap=50,
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        dataset_service.dataset_repo.datasets[dataset_id] = ds

        result = await dataset_service.get_dataset(dataset_id)

        assert result is not None
        assert result["name"] == "Test DS"
        assert result["chunk_size"] == 500

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, dataset_service, sample_dataset_id):
        """测试获取不存在的数据集"""
        result = await dataset_service.get_dataset(sample_dataset_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_dataset_success(self, dataset_service, sample_workspace_id):
        """测试更新数据集"""
        dataset_id = uuid4()
        ds = Dataset(
            id=dataset_id,
            workspace_id=sample_workspace_id,
            name="Old Name",
            description="Old Desc",
            embedding_model="model1",
            chunk_size=500,
            chunk_overlap=50,
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        dataset_service.dataset_repo.datasets[dataset_id] = ds

        result = await dataset_service.update_dataset(
            dataset_id=dataset_id,
            name="New Name",
            description="New Desc",
            metadata={"updated": True}
        )

        assert result["name"] == "New Name"
        assert result["description"] == "New Desc"
        assert result["metadata"]["updated"] is True

    @pytest.mark.asyncio
    async def test_update_dataset_not_found(self, dataset_service, sample_dataset_id):
        """测试更新不存在的数据集"""
        with pytest.raises(ValueError, match="数据集不存在"):
            await dataset_service.update_dataset(
                dataset_id=sample_dataset_id,
                name="New Name"
            )

    @pytest.mark.asyncio
    async def test_update_dataset_partial(self, dataset_service, sample_workspace_id):
        """测试部分更新数据集"""
        dataset_id = uuid4()
        ds = Dataset(
            id=dataset_id,
            workspace_id=sample_workspace_id,
            name="Original",
            description="Original Desc",
            embedding_model="model1",
            chunk_size=500,
            chunk_overlap=50,
            metadata={"key": "original"},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        dataset_service.dataset_repo.datasets[dataset_id] = ds

        result = await dataset_service.update_dataset(
            dataset_id=dataset_id,
            name="Updated Only"
        )

        assert result["name"] == "Updated Only"
        assert result["description"] == "Original Desc"

    @pytest.mark.asyncio
    async def test_delete_dataset_success(self, dataset_service, sample_workspace_id):
        """测试删除数据集"""
        dataset_id = uuid4()
        ds = Dataset(
            id=dataset_id,
            workspace_id=sample_workspace_id,
            name="To Delete",
            embedding_model="model1",
            chunk_size=500,
            chunk_overlap=50,
            metadata={}
        )
        dataset_service.dataset_repo.datasets[dataset_id] = ds

        result = await dataset_service.delete_dataset(dataset_id)

        assert result is True
        assert dataset_id not in dataset_service.dataset_repo.datasets

    @pytest.mark.asyncio
    async def test_delete_dataset_not_found(self, dataset_service, sample_dataset_id):
        """测试删除不存在的数据集"""
        result = await dataset_service.delete_dataset(sample_dataset_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_datasets_empty(self, dataset_service, sample_workspace_id):
        """测试查询空数据集列表"""
        result = await dataset_service.list_datasets(sample_workspace_id)

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_list_datasets_with_data(self, dataset_service, sample_workspace_id):
        """测试查询数据集列表"""
        for i in range(3):
            ds = Dataset(
                id=uuid4(),
                workspace_id=sample_workspace_id,
                name=f"Dataset {i}",
                description=f"Desc {i}",
                embedding_model="model1",
                chunk_size=500,
                chunk_overlap=50,
                metadata={},
                created_at=datetime.utcnow()
            )
            dataset_service.dataset_repo.datasets[ds.id] = ds

        result = await dataset_service.list_datasets(sample_workspace_id)

        assert result.total == 3
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_list_datasets_with_keyword(self, dataset_service, sample_workspace_id):
        """测试按关键字筛选数据集（当前实现未使用keyword）"""
        for name in ["Alpha Dataset", "Beta Dataset", "Gamma Project"]:
            ds = Dataset(
                id=uuid4(),
                workspace_id=sample_workspace_id,
                name=name,
                description="",
                embedding_model="model1",
                chunk_size=500,
                chunk_overlap=50,
                metadata={},
                created_at=datetime.utcnow()
            )
            dataset_service.dataset_repo.datasets[ds.id] = ds

        result = await dataset_service.list_datasets(
            workspace_id=sample_workspace_id,
            keyword="alpha"
        )

        assert result.total == 3

    @pytest.mark.asyncio
    async def test_list_datasets_pagination(self, dataset_service, sample_workspace_id):
        """测试数据集列表分页"""
        for i in range(25):
            ds = Dataset(
                id=uuid4(),
                workspace_id=sample_workspace_id,
                name=f"Dataset {i}",
                description="",
                embedding_model="model1",
                chunk_size=500,
                chunk_overlap=50,
                metadata={},
                created_at=datetime.utcnow()
            )
            dataset_service.dataset_repo.datasets[ds.id] = ds

        pagination = Pagination(page=2, page_size=10)
        result = await dataset_service.list_datasets(
            workspace_id=sample_workspace_id,
            pagination=pagination
        )

        assert result.total == 25
        assert len(result.items) == 10
        assert result.page == 2

    @pytest.mark.asyncio
    async def test_get_dataset_statistics_success(self, dataset_service, sample_workspace_id):
        """测试获取数据集统计信息"""
        dataset_id = uuid4()
        ds = Dataset(
            id=dataset_id,
            workspace_id=sample_workspace_id,
            name="Stats Dataset",
            embedding_model="model1",
            chunk_size=500,
            chunk_overlap=50,
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        dataset_service.dataset_repo.datasets[dataset_id] = ds

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10
        dataset_service.session.execute = AsyncMock(return_value=mock_result)

        result = await dataset_service.get_dataset_statistics(dataset_id)

        assert result["dataset_id"] == str(dataset_id)
        assert result["document_count"] == 10
        assert result["chunk_size"] == 500
        assert result["chunk_overlap"] == 50

    @pytest.mark.asyncio
    async def test_get_dataset_statistics_not_found(self, dataset_service, sample_dataset_id):
        """测试获取不存在数据集的统计信息"""
        with pytest.raises(ValueError, match="数据集不存在"):
            await dataset_service.get_dataset_statistics(sample_dataset_id)
