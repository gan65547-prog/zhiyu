#!/usr/bin/env python3
"""
手动添加会话权限字段到数据库
"""

import asyncio
import sys
sys.path.insert(0, '/Users/gan/Documents/ganfy/enterprise-rag-v2')

from sqlalchemy import text
from infrastructure.database.session import AsyncSessionLocal


async def add_conversation_permissions():
    """添加visibility和workspace_id字段"""
    
    async with AsyncSessionLocal() as session:
        try:
            # 检查visibility列是否存在
            result = await session.execute(text("""
                PRAGMA table_info(conversations)
            """))
            columns = [row[1] for row in result.fetchall()]
            
            print(f"当前conversations表列: {columns}")
            
            # 添加visibility列（如果不存在）
            if 'visibility' not in columns:
                print("✓ 添加 visibility 列...")
                await session.execute(text("""
                    ALTER TABLE conversations 
                    ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT 'private'
                """))
                print("  ✓ visibility 列已添加")
            else:
                print("✓ visibility 列已存在")
            
            # 添加workspace_id列（如果不存在）
            if 'workspace_id' not in columns:
                print("✓ 添加 workspace_id 列...")
                await session.execute(text("""
                    ALTER TABLE conversations 
                    ADD COLUMN workspace_id VARCHAR(36)
                """))
                
                # 回填workspace_id（使用SQLite子查询语法）
                print("✓ 回填 workspace_id 数据...")
                update_result = await session.execute(text("""
                    UPDATE conversations 
                    SET workspace_id = (
                        SELECT d.workspace_id 
                        FROM datasets d 
                        WHERE d.id = conversations.dataset_id
                    )
                    WHERE workspace_id IS NULL
                    AND dataset_id IN (SELECT id FROM datasets WHERE workspace_id IS NOT NULL)
                """))
                print(f"  ✓ 已更新记录")
            else:
                print("✓ workspace_id 列已存在")
            
            # 创建索引
            print("\n✓ 创建性能索引...")
            
            indexes_to_create = [
                ("idx_conversations_visibility", "CREATE INDEX IF NOT EXISTS idx_conversations_visibility ON conversations(visibility)"),
                ("idx_conversations_workspace_id", "CREATE INDEX IF NOT EXISTS idx_conversations_workspace_id ON conversations(workspace_id)"),
                ("idx_conversations_user_visibility", "CREATE INDEX IF NOT EXISTS idx_conversations_user_visibility ON conversations(user_id, visibility)"),
                ("idx_conversations_workspace_visibility", "CREATE INDEX IF NOT EXISTS idx_conversations_workspace_visibility ON conversations(workspace_id, visibility)")
            ]
            
            for index_name, sql in indexes_to_create:
                try:
                    await session.execute(text(sql))
                    print(f"  ✓ {index_name} 索引已创建")
                except Exception as e:
                    print(f"  ⚠ {index_name}: {e}")
            
            await session.commit()
            
            print("\n✅ 会话权限字段添加成功！")
            
            # 验证表结构
            result = await session.execute(text("""
                PRAGMA table_info(conversations)
            """))
            columns = [(row[1], row[2]) for row in result.fetchall()]
            print("\n更新后的表结构:")
            for col_name, col_type in columns:
                if col_name in ['visibility', 'workspace_id']:
                    print(f"  🆕 {col_name}: {col_type}")
                else:
                    print(f"    {col_name}: {col_type}")
                    
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(add_conversation_permissions())
