#!/usr/bin/env python3
"""测试密码验证"""

import sys
sys.path.insert(0, '/Users/gan/Documents/ganfy/enterprise-rag-v2')

import bcrypt
from services.utils.jwt import hash_password, verify_password

# 测试密码
password = "Admin123!@#"

# 使用bcrypt直接哈希
bcrypt_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"bcrypt hash: {bcrypt_hash}")

# 使用passlib哈希
passlib_hash = hash_password(password)
print(f"passlib hash: {passlib_hash}")

# 测试验证
print(f"\n验证bcrypt哈希:")
print(f"  bcrypt验证: {bcrypt.checkpw(password.encode('utf-8'), bcrypt_hash.encode('utf-8'))}")
print(f"  passlib验证: {verify_password(password, bcrypt_hash)}")

print(f"\n验证passlib哈希:")
print(f"  bcrypt验证: {bcrypt.checkpw(password.encode('utf-8'), passlib_hash.encode('utf-8'))}")
print(f"  passlib验证: {verify_password(password, passlib_hash)}")
