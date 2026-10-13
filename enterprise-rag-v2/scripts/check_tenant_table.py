#!/usr/bin/env python3
"""
检查租户表
"""

import sqlite3

def check_tenants():
    db_path = "enterprise_rag.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查租户表结构
    print("租户表结构:")
    cursor.execute("PRAGMA table_info(tenants)")
    for row in cursor.fetchall():
        print(row)
    
    # 检查租户数据
    print("\n租户表内容:")
    cursor.execute("SELECT id, name, contact_email, plan, status, created_at FROM tenants")
    for row in cursor.fetchall():
        print(row)
    
    conn.close()

if __name__ == "__main__":
    check_tenants()