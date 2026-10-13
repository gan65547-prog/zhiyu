#!/usr/bin/env python3
"""简单测试并发请求，验证500错误是否已修复"""

import subprocess
import time
import threading

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NzY0YTUwYy03MDI4LTQ2ZjYtOTkxMy1kYzM0MTcyMjdiY2MiLCJ1c2VybmFtZSI6InN1cGVyYWRtaW4iLCJlbWFpbCI6InN1cGVyYWRtaW5Ac3lzdGVtLmNvbSIsInRlbmFudF9pZCI6IjEwNjkxNmVlLTlmYWItNDBiZS1hNDM5LTQxNzY0OTU0YWRmZSIsImlzX3N1cGVydXNlciI6dHJ1ZSwiZXhwIjoxNzc1NjU1NzEyLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzc1NjU0ODEyfQ.Ng_9Kuwt_tloORc8Rsj3m1YwjTL7BW-wi1inI4LZsSw"

API_ENDPOINTS = [
    "http://localhost:8000/api/v1/datasets/",
    "http://localhost:8000/api/v1/workspaces/current"
]

def make_request(url):
    """发送单个请求"""
    cmd = [
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "-H", f"Authorization: Bearer {TOKEN}",
        url
    ]
    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        status = int(result.stdout.strip())
        end_time = time.time()
        print(f"{url} - Status: {status}, Time: {end_time - start_time:.2f}s")
        if status != 200:
            print(f"  Error output: {result.stderr}")
        return status
    except Exception as e:
        print(f"{url} - Error: {e}")
        return 500

def test_concurrent_requests():
    """测试并发请求"""
    print("开始测试并发请求...")
    print(f"测试的API端点: {API_ENDPOINTS}")
    print(f"使用的Token: {TOKEN[:20]}...")
    print()
    
    # 测试1: 5个并发请求
    print("=== 测试1: 5个并发请求 ===")
    threads = []
    results = []
    
    def collect_result(status):
        results.append(status)
    
    for i in range(5):
        for url in API_ENDPOINTS:
            thread = threading.Thread(
                target=lambda u: collect_result(make_request(u)),
                args=(url,)
            )
            threads.append(thread)
            thread.start()
    
    for thread in threads:
        thread.join()
    
    success_count = sum(1 for status in results if status == 200)
    total_count = len(results)
    print(f"成功: {success_count}/{total_count}")
    print()
    
    # 测试2: 连续3次请求（模拟刷新）
    print("=== 测试2: 连续3次请求 ===")
    for batch in range(3):
        print(f"批处理 {batch + 1}:")
        batch_results = []
        for url in API_ENDPOINTS:
            status = make_request(url)
            batch_results.append(status)
        success_count = sum(1 for status in batch_results if status == 200)
        total_count = len(batch_results)
        print(f"  成功: {success_count}/{total_count}")
        time.sleep(0.5)  # 短暂休息

if __name__ == "__main__":
    test_concurrent_requests()
