#!/usr/bin/env python3
"""
API测试脚本
测试后端API是否正常工作
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    return response.status_code == 200

def test_register():
    """测试用户注册"""
    print("\n=== 测试用户注册 ===")
    data = {
        "name": "测试用户",
        "email": "test@example.com",
        "password": "Test123!@#"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json=data,
        headers={"Content-Type": "application/json"}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    return response.status_code in [200, 201]

def test_login():
    """测试用户登录"""
    print("\n=== 测试用户登录 ===")
    data = {
        "email": "test@example.com",
        "password": "Test123!@#"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json=data,
        headers={"Content-Type": "application/json"}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    return response.status_code == 200

def test_api_docs():
    """测试API文档"""
    print("\n=== 测试API文档 ===")
    response = requests.get(f"{BASE_URL}/api/docs")
    print(f"状态码: {response.status_code}")
    print(f"API文档可访问: {'是' if response.status_code == 200 else '否'}")
    return response.status_code == 200

if __name__ == "__main__":
    print("开始测试后端API...")
    
    results = {
        "健康检查": test_health(),
        "API文档": test_api_docs(),
        "用户注册": test_register(),
        "用户登录": test_login(),
    }
    
    print("\n" + "="*50)
    print("测试结果汇总:")
    print("="*50)
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    print("\n" + ("🎉 所有测试通过！" if all_passed else "⚠️ 部分测试失败"))
