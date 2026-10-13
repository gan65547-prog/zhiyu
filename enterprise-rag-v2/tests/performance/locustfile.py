"""
Locust性能测试配置

用于负载测试的Locust任务定义
"""

from locust import HttpUser, task, between, events
import random
import json


class ChatUser(HttpUser):
    """聊天用户模拟"""
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """用户开始时执行：登录获取token"""
        email = f"loadtest_{random.randint(1, 10000)}@example.com"
        password = "TestPass123!"

        response = self.client.post("/api/v1/auth/register", json={
            "username": f"user_{random.randint(1, 10000)}",
            "email": email,
            "password": password
        })

        if response.status_code == 200:
            login_response = self.client.post("/api/v1/auth/login", json={
                "username": email,
                "password": password
            })
            if login_response.status_code == 200:
                data = login_response.json()
                if data.get("code") == 0:
                    self.token = data["data"]["access_token"]

    @task(3)
    def chat_query(self):
        """发送聊天请求"""
        if not self.token:
            return

        dataset_id = "test-dataset-id"
        queries = [
            "What is this document about?",
            "Can you summarize the key points?",
            "What are the main conclusions?",
            "Explain this in detail",
            "What evidence is provided?"
        ]

        self.client.post(
            f"/api/v1/chat/{dataset_id}/chat",
            json={"query": random.choice(queries)},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def search_knowledge_base(self):
        """搜索知识库"""
        if not self.token:
            return

        dataset_id = "test-dataset-id"
        queries = ["AI", "machine learning", "data processing", "system architecture"]

        self.client.get(
            f"/api/v1/datasets/{dataset_id}/hit-testing",
            params={"query": random.choice(queries), "top_k": 5},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def list_conversations(self):
        """获取会话列表"""
        if not self.token:
            return

        dataset_id = "test-dataset-id"

        self.client.get(
            f"/api/v1/chat/{dataset_id}/conversations",
            headers={"Authorization": f"Bearer {self.token}"}
        )


class DatasetUser(HttpUser):
    """数据集管理用户模拟"""
    wait_time = between(2, 5)
    token = None
    dataset_id = None

    def on_start(self):
        """用户开始时执行：登录并创建数据集"""
        email = f"dataset_test_{random.randint(1, 1000)}@example.com"
        password = "TestPass123!"

        self.client.post("/api/v1/auth/register", json={
            "username": f"dataset_user_{random.randint(1, 1000)}",
            "email": email,
            "password": password
        })

        login_response = self.client.post("/api/v1/auth/login", json={
            "username": email,
            "password": password
        })

        if login_response.status_code == 200:
            data = login_response.json()
            if data.get("code") == 0:
                self.token = data["data"]["access_token"]

                create_dataset = self.client.post(
                    "/api/v1/datasets",
                    json={
                        "name": f"LoadTestDataset_{random.randint(1, 1000)}",
                        "description": "Dataset for load testing"
                    },
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                if create_dataset.status_code == 200:
                    result = create_dataset.json()
                    if result.get("code") == 0:
                        self.dataset_id = result["data"]["id"]

    @task(3)
    def upload_document(self):
        """上传文档"""
        if not self.token or not self.dataset_id:
            return

        file_content = b"This is test document content for load testing. " * 100
        files = {
            "file": ("test_doc.txt", file_content, "text/plain")
        }

        self.client.post(
            f"/api/v1/documents/{self.dataset_id}/upload",
            files=files,
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def list_documents(self):
        """列出文档"""
        if not self.token or not self.dataset_id:
            return

        self.client.get(
            f"/api/v1/documents/{self.dataset_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def get_dataset_info(self):
        """获取数据集信息"""
        if not self.token or not self.dataset_id:
            return

        self.client.get(
            f"/api/v1/datasets/{self.dataset_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )


class AuthUser(HttpUser):
    """认证流程用户模拟"""
    wait_time = between(1, 2)

    @task(5)
    def login(self):
        """登录"""
        self.client.post("/api/v1/auth/login", json={
            "username": "testuser@example.com",
            "password": "TestPass123!"
        })

    @task(2)
    def register(self):
        """注册"""
        email = f"newuser_{random.randint(1, 100000)}@example.com"
        self.client.post("/api/v1/auth/register", json={
            "username": f"user_{random.randint(1, 100000)}",
            "email": email,
            "password": "TestPass123!"
        })

    @task(1)
    def refresh_token(self):
        """刷新token"""
        refresh_token = "dummy_refresh_token"
        self.client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的钩子"""
    print("Performance test is starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的钩子"""
    print("Performance test is stopping...")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"P95 response time: {environment.stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"P99 response time: {environment.stats.total.get_response_time_percentile(0.99):.2f}ms")


if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py --host=http://localhost:8000")
