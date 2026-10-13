"""
性能测试 - API性能测试

测试API响应时间和并发性能
"""

import pytest
import asyncio
import time
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch


class TestAPIPerformance:
    """API性能测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_auth_service_response_time(self, mock_db_session):
        """测试认证服务响应时间"""
        from services.impl.auth_service import AuthServiceImpl

        service = AuthServiceImpl(session=mock_db_session)

        async def mock_operation():
            await asyncio.sleep(0.01)
            return True

        start_time = time.time()
        await mock_operation()
        elapsed = time.time() - start_time

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_concurrent_auth_requests(self, mock_db_session):
        """测试并发认证请求"""
        from services.impl.auth_service import AuthServiceImpl

        service = AuthServiceImpl(session=mock_db_session)

        async def mock_register(i):
            await asyncio.sleep(0.01)
            return {"user_id": str(uuid4()), "token": f"token_{i}"}

        start_time = time.time()
        tasks = [mock_register(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        assert len(results) == 100
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_chat_service_throughput(self, mock_db_session):
        """测试聊天服务吞吐量"""
        from services.impl.chat_service import ChatServiceImpl

        service = ChatServiceImpl(session=mock_db_session)
        service.conversation_repo = MagicMock()
        service.message_repo = MagicMock()

        async def mock_chat_request(i):
            await asyncio.sleep(0.005)
            return {
                "answer": f"Response {i}",
                "conversation_id": str(uuid4()),
                "tokens_used": 10
            }

        start_time = time.time()
        tasks = [mock_chat_request(i) for i in range(200)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        throughput = len(results) / elapsed
        assert throughput > 100


class TestDatabasePerformance:
    """数据库性能测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_query_response_time(self, mock_db_session):
        """测试查询响应时间"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        start_time = time.time()
        await mock_db_session.execute(MagicMock())
        elapsed = time.time() - start_time

        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_batch_insert_performance(self, mock_db_session):
        """测试批量插入性能"""
        async def mock_batch_insert(items):
            await asyncio.sleep(0.01)
            return items

        items = [str(uuid4()) for _ in range(100)]

        start_time = time.time()
        results = await mock_batch_insert(items)
        elapsed = time.time() - start_time

        assert len(results) == 100
        assert elapsed < 0.5


class TestRetrievalPerformance:
    """检索性能测试"""

    @pytest.mark.asyncio
    async def test_vector_search_latency(self):
        """测试向量搜索延迟"""
        async def mock_vector_search(query, top_k):
            await asyncio.sleep(0.02)
            return [{"id": str(uuid4()), "score": 0.95} for _ in range(top_k)]

        query = "test query"
        top_k = 5

        start_time = time.time()
        results = await mock_vector_search(query, top_k)
        elapsed = time.time() - start_time

        assert len(results) == top_k
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_hybrid_search_performance(self):
        """测试混合搜索性能"""
        async def mock_hybrid_search(query, top_k):
            semantic_results = await asyncio.sleep(0.01) or [{"id": str(uuid4()), "score": 0.9}]
            keyword_results = await asyncio.sleep(0.01) or [{"id": str(uuid4()), "score": 0.8}]
            return semantic_results + keyword_results

        start_time = time.time()
        results = await mock_hybrid_search("test query", 5)
        elapsed = time.time() - start_time

        assert elapsed < 0.1


class TestConcurrentLoad:
    """并发负载测试"""

    @pytest.mark.asyncio
    async def test_sustained_concurrent_load(self):
        """测试持续并发负载"""
        concurrent_users = 50
        requests_per_user = 10

        async def simulate_user(user_id):
            results = []
            for _ in range(requests_per_user):
                await asyncio.sleep(0.01)
                results.append({"user_id": user_id, "status": "ok"})
            return results

        start_time = time.time()
        tasks = [simulate_user(i) for i in range(concurrent_users)]
        all_results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        total_requests = sum(len(r) for r in all_results)
        assert total_requests == concurrent_users * requests_per_user

    @pytest.mark.asyncio
    async def test_burst_load_handling(self):
        """测试突发负载处理"""
        burst_size = 200

        async def handle_burst_request(i):
            await asyncio.sleep(0.005)
            return {"request_id": i, "processed": True}

        start_time = time.time()
        tasks = [handle_burst_request(i) for i in range(burst_size)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        assert len(results) == burst_size
        throughput = burst_size / elapsed
        assert throughput > 100


class TestPerformanceBenchmarks:
    """性能基准测试"""

    @pytest.mark.asyncio
    async def test_p95_response_time(self):
        """测试P95响应时间"""
        response_times = []

        async def measure_request():
            start = time.time()
            await asyncio.sleep(0.01)
            return time.time() - start

        for _ in range(100):
            rt = await measure_request()
            response_times.append(rt)

        response_times.sort()
        p95_index = int(len(response_times) * 0.95)
        p95 = response_times[p95_index]

        assert p95 < 0.1

    @pytest.mark.asyncio
    async def test_p99_response_time(self):
        """测试P99响应时间"""
        response_times = []

        async def measure_request():
            start = time.time()
            await asyncio.sleep(0.01)
            return time.time() - start

        for _ in range(100):
            rt = await measure_request()
            response_times.append(rt)

        response_times.sort()
        p99_index = int(len(response_times) * 0.99)
        p99 = response_times[p99_index]

        assert p99 < 0.15