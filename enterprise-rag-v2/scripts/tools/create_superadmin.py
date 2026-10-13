#!/usr/bin/env python
"""创建超级管理员账户"""

import sqlite3
import bcrypt
import os
import secrets
import string
from uuid import uuid4
from datetime import datetime

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "superadmin@system.com").strip().lower()
SUPERADMIN_USERNAME = os.getenv("SUPERADMIN_USERNAME", "superadmin").strip() or "superadmin"
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "").strip()


def generate_secure_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(ch.islower() for ch in candidate)
            and any(ch.isupper() for ch in candidate)
            and any(ch.isdigit() for ch in candidate)
            and any(ch in "!@#$%^&*()-_=+" for ch in candidate)
        ):
            return candidate


# 连接到数据库
conn = sqlite3.connect('enterprise_rag.db')
cursor = conn.cursor()

# 检查用户是否已存在
cursor.execute('SELECT id FROM users WHERE email = ?', (SUPERADMIN_EMAIL,))
existing_user = cursor.fetchone()

if existing_user:
    print('超级管理员账户已存在:', existing_user[0])
else:
    raw_password = SUPERADMIN_PASSWORD or generate_secure_password()
    # 生成密码哈希
    hashed_password = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # 生成用户ID
    user_id = str(uuid4())
    
    # 获取默认租户ID
    cursor.execute('SELECT id FROM tenants WHERE contact_email = ?', ('admin@default.com',))
    tenant = cursor.fetchone()
    if not tenant:
        print('找不到默认租户！')
        conn.close()
        exit(1)
    tenant_id = tenant[0]
    
    # 插入用户数据
    cursor.execute('''
        INSERT INTO users (
            id, tenant_id, username, email, hashed_password, 
            is_active, is_superuser, extra_metadata, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        tenant_id,
        SUPERADMIN_USERNAME,
        SUPERADMIN_EMAIL,
        hashed_password,
        1,  # is_active
        1,  # is_superuser
        '{"is_default": true}',
        datetime.utcnow(),
        datetime.utcnow()
    ))
    
    # 提交事务
    conn.commit()
    print('超级管理员账户创建成功！')
    print(f'  邮箱: {SUPERADMIN_EMAIL}')
    if SUPERADMIN_PASSWORD:
        print('  密码: 使用 SUPERADMIN_PASSWORD 环境变量提供（已生效）')
    else:
        print(f'  一次性初始密码: {raw_password}')
        print('  请首次登录后立即在个人中心修改密码。')
    print(f'  用户ID: {user_id}')

# 关闭连接
conn.close()
