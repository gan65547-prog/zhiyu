#!/usr/bin/env python3
"""
查看 platform_app_configs 表内容
"""

import sqlite3

conn = sqlite3.connect('enterprise_rag.db')
cursor = conn.cursor()

# 查看表结构
print("platform_app_configs 表结构:")
cursor.execute('PRAGMA table_info(platform_app_configs)')
for row in cursor.fetchall():
    print(row)

print("\nplatform_app_configs 表内容:")
cursor.execute('''
    SELECT id, platform, app_id, tenant_id, display_name, is_active, created_at 
    FROM platform_app_configs 
    LIMIT 10
''')

rows = cursor.fetchall()
if rows:
    for row in rows:
        print(row)
else:
    print("表为空")

cursor.close()
conn.close()