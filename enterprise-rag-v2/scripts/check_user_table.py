#!/usr/bin/env python3
"""
检查用户表
"""

import sqlite3

def check_users():
    db_path = "enterprise_rag.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查用户表结构
    print("用户表结构:")
    cursor.execute("PRAGMA table_info(users)")
    for row in cursor.fetchall():
        print(row)
    
    # 检查用户数据
    print("\n用户表内容:")
    cursor.execute("SELECT id, email, display_name, tenant_id, is_superuser, is_active FROM users")
    for row in cursor.fetchall():
        print(row)
    
    conn.close()

if __name__ == "__main__":
    check_users()