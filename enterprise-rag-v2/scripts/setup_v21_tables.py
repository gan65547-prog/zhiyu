import sqlite3
import os

db_path = './enterprise_rag.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. platform_app_configs
cur.execute("""
CREATE TABLE IF NOT EXISTS platform_app_configs (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    app_id TEXT NOT NULL,
    encrypted_credentials TEXT NOT NULL,
    display_name TEXT,
    verification_token TEXT,
    encrypt_key TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    config TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

try:
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_pac_platform_app ON platform_app_configs(platform, app_id)")
except Exception:
    pass

cur.execute("CREATE INDEX IF NOT EXISTS idx_pac_tenant ON platform_app_configs(tenant_id)")

# 2. platform_users add app_config_id
try:
    cur.execute("ALTER TABLE platform_users ADD COLUMN app_config_id TEXT")
    print("platform_users.app_config_id column ADDED")
except sqlite3.OperationalError as e:
    if "duplicate" in str(e).lower():
        print("platform_users.app_config_id column EXISTS")
    else:
        raise

try:
    cur.execute("CREATE INDEX IF NOT EXISTS idx_platform_users_app_config ON platform_users(app_config_id)")
except Exception:
    pass

conn.commit()

tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%platform%'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")

cols = cur.execute("PRAGMA table_info(platform_app_configs)").fetchall()
print(f"platform_app_configs columns: {len(cols)}")

cols2 = cur.execute("PRAGMA table_info(platform_users)").fetchall()
names = [c[1] for c in cols2]
print(f"platform_users has app_config_id: {'app_config_id' in names}")

conn.close()
print("\nDB READY OK")
