"""
性能测试套件

测试RAG系统各组件的性能指标
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.cache_service import CacheService, MemoryCacheBackend
from services.metrics_service import MetricsCollector, RAGMetrics
from core.rag.collection_manager import CollectionManager


class TestCachePerformance:
    """缓存性能测试"""
    
    @pytest.fixture
    def cache_service(self):
        backend = MemoryCacheBackend(max_size=1000)
        return CacheService(backend=backend)
    
    @pytest.mark.asyncio
    async def test_cache_set_get_performance(self, cache_service):
        """测试缓存设置和获取性能"""
        iterations = 1000
        
        start_time = time.time()
        
        for i in range(iterations):
            await cache_service.set(f"key_{i}", f"value_{i}")
        
        set_duration = time.time() - start_time
        
        start_time = time.time()
        
        for i in range(iterations):
            await cache_service.get(f"key_{i}")
        
        get_duration = time.time() - start_time
        
        assert set_duration < 1.0
        assert get_duration < 0.5
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate(self, cache_service):
        """测试缓存命中率"""
        for i in range(100):
            await cache_service.set(f"key_{i}", f"value_{i}")
        
        for i in range(100):
            await cache_service.get(f"key_{i}")
        
        for i in range(100):
            await cache_service.get(f"key_{i}")
        
        stats = cache_service.get_stats()
        
        assert stats["hit_count"] == 200
        assert stats["miss_count"] == 0
        assert stats["hit_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, cache_service):
        """测试缓存TTL过期"""
        await cache_service.set("ttl_key", "ttl_value", ttl=1)
        
        value = await cache_service.get("ttl_key")
        assert value == "ttl_value"
        
        await asyncio.sleep(1.1)
        
        value = await cache_service.get("ttl_key")
        assert value is None


class TestMetricsPerformance:
    """指标收集性能测试"""
    
    @pytest.fixture
    def metrics_collector(self):
        return MetricsCollector()
    
    def test_counter_performance(self, metrics_collector):
        """测试计数器性能"""
        iterations = 10000
        
        start_time = time.time()
        
        for i in range(iterations):
            metrics_collector.counter("test_counter", 1, {"iteration": str(i % 100)})
        
        duration = time.time() - start_time
        
        assert duration < 0.5
    
    def test_gauge_performance(self, metrics_collector):
        """测试仪表性能"""
        iterations = 10000
        
        start_time = time.time()
        
        for i in range(iterations):
            metrics_collector.gauge("test_gauge", i, {"iteration": str(i % 100)})
        
        duration = time.time() - start_time
        
        assert duration < 0.5
    
    def test_histogram_performance(self, metrics_collector):
        """测试直方图性能"""
        iterations = 10000
        
        start_time = time.time()
        
        for i in range(iterations):
            metrics_collector.histogram("test_histogram", i * 0.001)
        
        duration = time.time() - start_time
        
        assert duration < 1.0
    
    def test_prometheus_format_performance(self, metrics_collector):
        """测试Prometheus格式性能"""
        for i in range(1000):
            metrics_collector.counter("test_metric", i)
        
        start_time = time.time()
        
        for _ in range(100):
            metrics_collector.to_prometheus_format()
        
        duration = time.time() - start_time
        
        assert duration < 0.1


class TestCollectionManagerPerformance:
    """集合管理器性能测试"""
    
    @pytest.fixture
    def mock_vector_store(self):
        store = AsyncMock()
        store.collection_exists = AsyncMock(return_value=True)
        store.create_collection = AsyncMock(return_value=True)
        return store
    
    @pytest.mark.asyncio
    async def test_ensure_collection_performance(self, mock_vector_store):
        """测试确保集合存在性能"""
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        iterations = 100
        
        start_time = time.time()
        
        for _ in range(iterations):
            await manager.ensure_collection_exists()
        
        duration = time.time() - start_time
        
        assert duration < 1.0
    
    @pytest.mark.asyncio
    async def test_diagnose_performance(self, mock_vector_store):
        """测试诊断性能"""
        manager = CollectionManager(
            collection_name="test_collection",
            vector_store=mock_vector_store
        )
        
        iterations = 50
        
        start_time = time.time()
        
        for _ in range(iterations):
                await manager.diagnose()
        
        duration = time.time() - start_time
        
        assert duration < 5.0


class TestConcurrencyPerformance:
    """并发性能测试"""

    @pytest.fixture
    def cache_service(self):
        backend = MemoryCacheBackend(max_size=2000)
        return CacheService(backend=backend)

    @pytest.fixture
    def metrics_collector(self):
        return MetricsCollector()
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, cache_service):
        """测试并发缓存操作"""
        async def cache_operation(operation_id: int):
            for i in range(100):
                key = f"concurrent_key_{operation_id}_{i}"
                await cache_service.set(key, f"value_{i}")
                await cache_service.get(key)
        
        start_time = time.time()
        
        tasks = [cache_operation(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        
        assert duration < 2.0
    
    @pytest.mark.asyncio
    async def test_concurrent_metrics_operations(self, metrics_collector):
        """测试并发指标操作"""
        async def metrics_operation(operation_id: int):
            for i in range(100):
                metrics_collector.counter(
                    f"concurrent_counter_{operation_id}",
                    1,
                    {"op": str(operation_id)}
                )
                metrics_collector.gauge(
                    f"concurrent_gauge_{operation_id}",
                    i,
                    {"op": str(operation_id)}
                )
        
        start_time = time.time()
        
        tasks = [metrics_operation(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        
        assert duration < 1.0


class TestMemoryUsage:
    """内存使用测试"""
    
    @pytest.mark.asyncio
    async def test_cache_memory_usage(self):
        """测试缓存内存使用"""
        backend = MemoryCacheBackend(max_size=10000)
        cache = CacheService(backend=backend)
        
        for i in range(10000):
            await cache.set(f"large_key_{i}", "x" * 1000)
        
        stats = backend.get_stats()
        
        assert stats["size"] == 10000
        assert stats["memory_usage"] > 0
        
        await cache.clear()
        
        stats = backend.get_stats()
        assert stats["size"] == 0
    
    @pytest.mark.asyncio
    async def test_metrics_memory_usage(self):
        """测试指标内存使用"""
        collector = MetricsCollector()
        
        for i in range(10000):
            collector.counter(f"metric_{i}", i)
        
        prometheus_output = collector.to_prometheus_format()
        
        assert len(prometheus_output) > 0
        
        collector.reset()
        
        prometheus_output = collector.to_prometheus_format()
        assert prometheus_output == ""
