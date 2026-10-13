#!/usr/bin/env python3
"""测试数据集详情API"""

import httpx
import json

async def test_dataset_detail():
    """测试数据集详情API"""
    # 先获取token
    login_url = "http://localhost:8000/api/v1/auth/login"
    login_data = {
        "email": "admin@default.com",
        "password": "Admin123!@#"
    }
    
    async with httpx.AsyncClient() as client:
        # 登录获取token
        login_response = await client.post(login_url, json=login_data)
        print(f"Login status: {login_response.status_code}")
        
        if login_response.status_code != 200:
            print("登录失败")
            return
        
        token = login_response.json()['data']['access_token']
        
        # 获取数据集列表
        datasets_url = "http://localhost:8000/api/v1/datasets/"
        datasets_response = await client.get(
            datasets_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"\nDatasets status: {datasets_response.status_code}")
        datasets = datasets_response.json()['data']['items']
        
        if not datasets:
            print("没有数据集")
            return
        
        # 测试第一个数据集的详情
        dataset_id = datasets[0]['id']
        detail_url = f"http://localhost:8000/api/v1/datasets/{dataset_id}"
        
        detail_response = await client.get(
            detail_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"\nDataset detail status: {detail_response.status_code}")
        dataset_detail = detail_response.json()
        
        print("\n数据集详情:")
        print(f"名称: {dataset_detail['data']['name']}")
        print(f"文档数量: {dataset_detail['data']['document_count']}")
        print(f"统计信息: {dataset_detail['data'].get('statistics', {})}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_dataset_detail())
