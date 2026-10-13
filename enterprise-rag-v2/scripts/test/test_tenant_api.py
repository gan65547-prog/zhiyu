#!/usr/bin/env python
"""测试租户 API"""

import requests
import json

# 先登录获取 token
login_response = requests.post('http://localhost:8000/api/v1/auth/login', json={
    'email': 'admin@default.com',
    'password': 'Admin123!@#'
})
print('Login response:', login_response.status_code)
print('Login response body:', json.dumps(login_response.json(), indent=2, ensure_ascii=False))

if login_response.status_code == 200:
    token = login_response.json().get('data', {}).get('access_token')
    print('Token:', token)
    
    # 使用 token 获取租户列表
    headers = {'Authorization': f'Bearer {token}'}
    tenant_response = requests.get('http://localhost:8000/api/v1/tenants/', headers=headers)
    print('Tenant list response:', tenant_response.status_code)
    print('Tenant list response body:', json.dumps(tenant_response.json(), indent=2, ensure_ascii=False))
