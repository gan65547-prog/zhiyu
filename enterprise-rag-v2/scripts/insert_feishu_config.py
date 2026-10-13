#!/usr/bin/env python3
"""
插入飞书配置到 platform_app_configs 表
"""

import os
import sqlite3
import json
import uuid
from cryptography.fernet import Fernet

# 飞书配置信息
FEISHU_CONFIG = {
    "tenant_id": 1,  # 第一个租户 (INTEGER 类型)
    "platform": "feishu",
    "app_id": os.environ["FEISHU_APP_ID"],
    "app_secret": os.environ["FEISHU_APP_SECRET"],
    "verification_token": os.environ["FEISHU_VERIFICATION_TOKEN"],
    "encrypt_key": os.environ["FEISHU_ENCRYPT_KEY"],
    "display_name": "测试企业"
}

def get_encryption_key():
    """从环境变量获取加密密钥"""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # 尝试从 .env 文件读取
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ENCRYPTION_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not found")
    return key

def encrypt_credentials(app_secret, verification_token, encrypt_key):
    """加密凭证"""
    key = get_encryption_key()
    cipher = Fernet(key.encode())
    
    credentials = {
    "app_secret": os.environ["FEISHU_APP_SECRET"],
    "verification_token": os.environ["FEISHU_VERIFICATION_TOKEN"],
    "encrypt_key": os.environ["FEISHU_ENCRYPT_KEY"],
    }
    
    credentials_json = json.dumps(credentials, ensure_ascii=False)
    encrypted = cipher.encrypt(credentials_json.encode())
    return encrypted.decode()

def insert_config():
    """插入配置到数据库"""
    db_path = "enterprise_rag.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 加密凭证
    encrypted_credentials = encrypt_credentials(
        FEISHU_CONFIG["app_secret"],
        FEISHU_CONFIG["verification_token"],
        FEISHU_CONFIG["encrypt_key"]
    )
    
    # 检查是否已存在相同的 platform + app_id
    cursor.execute(
        "SELECT id FROM platform_app_configs WHERE platform = ? AND app_id = ?",
        (FEISHU_CONFIG["platform"], FEISHU_CONFIG["app_id"])
    )
    existing = cursor.fetchone()
    
    if existing:
        print(f"配置已存在，ID: {existing[0]}")
        conn.close()
        return
    
    # 生成 UUID 作为配置 ID
    config_id = str(uuid.uuid4())
    
    # 插入新配置
    cursor.execute(
        """
        INSERT INTO platform_app_configs (
            id, tenant_id, platform, app_id, encrypted_credentials, 
            display_name, verification_token, encrypt_key, 
            is_active, config, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            config_id,
            FEISHU_CONFIG["tenant_id"],
            FEISHU_CONFIG["platform"],
            FEISHU_CONFIG["app_id"],
            encrypted_credentials,
            FEISHU_CONFIG["display_name"],
            FEISHU_CONFIG["verification_token"],  # 明文存储用于快速验证
            FEISHU_CONFIG["encrypt_key"],  # 明文存储
            True,
            json.dumps({"auto_register": True}, ensure_ascii=False)
        )
    )
    
    conn.commit()
    conn.close()
    
    print(f"✅ 飞书配置插入成功，ID: {config_id}")
    print(f"平台: {FEISHU_CONFIG['platform']}")
    print(f"App ID: {FEISHU_CONFIG['app_id']}")
    print(f"租户: {FEISHU_CONFIG['tenant_id']}")
    print(f"显示名称: {FEISHU_CONFIG['display_name']}")

if __name__ == "__main__":
    try:
        insert_config()
    except Exception as e:
        print(f"❌ 出错: {e}")
        import traceback
        traceback.print_exc()
