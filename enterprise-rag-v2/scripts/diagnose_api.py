#!/usr/bin/env python3
"""详细诊断API问题"""
import httpx
import json

BASE = 'http://127.0.0.1:8000'

print('='*60)
print('详细诊断认证端点')
print('='*60)

tests = [
    ('不存在的用户登录', 'POST', '/api/v1/auth/login', {'email':'nonexistent@test.com','password':'test123456'}),
    ('空body登录', 'POST', '/api/v1/auth/login', {}),
    ('无效邮箱', 'POST', '/api/v1/auth/login', {'email':'invalid','password':'test'}),
    ('用户注册', 'POST', '/api/v1/auth/register', {'email':'diag@test.com','password':'Test123456','name':'diag'}),
    ('refresh token', 'POST', '/api/v1/auth/refresh', {}),
]

for name, method, path, data in tests:
    print(f'\n{name}:')
    print(f'  {method} {path}')
    try:
        if method == 'POST':
            r = httpx.post(f'{BASE}{path}', json=data, timeout=10)
        else:
            r = httpx.get(f'{BASE}{path}', timeout=10)
        print(f'  状态码: {r.status_code}')
        print(f'  响应: {r.text[:300]}')
    except Exception as e:
        print(f'  错误: {e}')

# 测试GET端点
print('\n\nGET端点测试:')
get_tests = [
    ('/api/v1/auth/me', '当前用户'),
    ('/api/v1/users', '用户列表'),
    ('/api/v1/tenants', '租户列表'),
    ('/api/v1/workspaces', '工作空间'),
]

for path, name in get_tests:
    print(f'\n{name} ({path}):')
    try:
        r = httpx.get(f'{BASE}{path}', timeout=10)
        print(f'  状态码: {r.status_code}')
        print(f'  响应: {r.text[:150]}')
    except Exception as e:
        print(f'  错误: {e}')