#!/usr/bin/env python3
"""创建测试token"""

import sys
sys.path.insert(0, '/Users/gan/Documents/ganfy/enterprise-rag-v2')

from services.utils.jwt import create_access_token

# 创建一个新的测试token
def create_test_token():
    # 使用一个有效的用户ID和租户ID
    data = {
        "sub": "5764a50c-7028-46f6-9913-dc3417227bcc",  # superadmin
        "username": "superadmin",
        "email": "superadmin@system.com",
        "tenant_id": "106916ee-9fab-40be-a439-41764954adfe",
        "is_superuser": True
    }
    
    token = create_access_token(data)
    return token

if __name__ == "__main__":
    token = create_test_token()
    print(f"Test Token: {token}")
