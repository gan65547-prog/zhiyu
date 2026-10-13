"""
数据库种子数据脚本

创建多个测试租户和用户，用于演示不同权限场景
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from uuid import uuid4
from datetime import datetime
import bcrypt
from sqlalchemy import select, insert

from infrastructure.database.session import engine
from infrastructure.database.models import Base, Tenant, User, Workspace, WorkspaceMember


async def seed_database():
    """生成种子数据"""
    print("开始生成种子数据...\n")

    async with engine.begin() as conn:
        # ============ 1. 创建两个测试租户 ============
        
        # 租户1: ABC科技公司
        result = await conn.execute(
            select(Tenant).where(Tenant.contact_email == "admin@abctech.com")
        )
        abc_tenant = result.scalar_one_or_none()
        
        if not abc_tenant:
            abc_tenant_id = str(uuid4())
            await conn.execute(
                insert(Tenant).values(
                    id=abc_tenant_id,
                    name="ABC科技公司",
                    contact_email="admin@abctech.com",
                    plan="pro",
                    status="active",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建租户: ABC科技公司 (ID: {abc_tenant_id})")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(Tenant.id).where(Tenant.contact_email == "admin@abctech.com")
            )
            abc_tenant_id = result.scalar_one_or_none()
            print(f"ℹ️  租户已存在: ABC科技公司")
        
        # 租户2: XYZ教育集团
        result = await conn.execute(
            select(Tenant).where(Tenant.contact_email == "admin@xyzedu.com")
        )
        xyz_tenant = result.scalar_one_or_none()
        
        if not xyz_tenant:
            xyz_tenant_id = str(uuid4())
            await conn.execute(
                insert(Tenant).values(
                    id=xyz_tenant_id,
                    name="XYZ教育集团",
                    contact_email="admin@xyzedu.com",
                    plan="enterprise",
                    status="active",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建租户: XYZ教育集团 (ID: {xyz_tenant_id})")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(Tenant.id).where(Tenant.contact_email == "admin@xyzedu.com")
            )
            xyz_tenant_id = result.scalar_one_or_none()
            print(f"ℹ️  租户已存在: XYZ教育集团")

        # ============ 2. 创建用户 ============
        
        # 用户1: 超级管理员 (跨租户管理)
        result = await conn.execute(
            select(User).where(User.email == "superadmin@system.com")
        )
        superadmin_user = result.scalar_one_or_none()
        
        if not superadmin_user:
            superadmin_id = str(uuid4())
            hashed_pw = bcrypt.hashpw("SuperAdmin123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                insert(User).values(
                    id=superadmin_id,
                    tenant_id=abc_tenant_id,  # 属于ABC科技公司
                    username="superadmin",
                    email="superadmin@system.com",
                    hashed_password=hashed_pw,
                    is_active=True,
                    is_superuser=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建超级管理员: superadmin@system.com / SuperAdmin123!@#")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(User.id).where(User.email == "superadmin@system.com")
            )
            superadmin_id = result.scalar_one_or_none()
            print(f"ℹ️  超级管理员已存在: superadmin@system.com")

        # ============ ABC科技公司的用户 ============
        
        # 用户2: ABC科技 - 工作空间所有者 (OWNER)
        result = await conn.execute(
            select(User).where(User.email == "zhangsan@abctech.com")
        )
        zhangsan_user = result.scalar_one_or_none()
        
        if not zhangsan_user:
            zhangsan_id = str(uuid4())
            hashed_pw = bcrypt.hashpw("Zhangsan123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                insert(User).values(
                    id=zhangsan_id,
                    tenant_id=abc_tenant_id,
                    username="zhangsan",
                    email="zhangsan@abctech.com",
                    hashed_password=hashed_pw,
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建用户: zhangsan@abctech.com / Zhangsan123!@# (OWNER)")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(User.id).where(User.email == "zhangsan@abctech.com")
            )
            zhangsan_id = result.scalar_one_or_none()
            print(f"ℹ️  用户已存在: zhangsan@abctech.com")

        # 用户3: ABC科技 - 管理员 (ADMIN)
        result = await conn.execute(
            select(User).where(User.email == "lisi@abctech.com")
        )
        lisi_user = result.scalar_one_or_none()
        
        if not lisi_user:
            lisi_id = str(uuid4())
            hashed_pw = bcrypt.hashpw("Lisi123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                insert(User).values(
                    id=lisi_id,
                    tenant_id=abc_tenant_id,
                    username="lisi",
                    email="lisi@abctech.com",
                    hashed_password=hashed_pw,
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建用户: lisi@abctech.com / Lisi123!@# (ADMIN)")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(User.id).where(User.email == "lisi@abctech.com")
            )
            lisi_id = result.scalar_one_or_none()
            print(f"ℹ️  用户已存在: lisi@abctech.com")

        # 用户4: ABC科技 - 普通成员 (MEMBER)
        result = await conn.execute(
            select(User).where(User.email == "wangwu@abctech.com")
        )
        wangwu_user = result.scalar_one_or_none()
        
        if not wangwu_user:
            wangwu_id = str(uuid4())
            hashed_pw = bcrypt.hashpw("Wangwu123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                insert(User).values(
                    id=wangwu_id,
                    tenant_id=abc_tenant_id,
                    username="wangwu",
                    email="wangwu@abctech.com",
                    hashed_password=hashed_pw,
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建用户: wangwu@abctech.com / Wangwu123!@# (MEMBER)")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(User.id).where(User.email == "wangwu@abctech.com")
            )
            wangwu_id = result.scalar_one_or_none()
            print(f"ℹ️  用户已存在: wangwu@abctech.com")

        # 用户5: ABC科技 - 查看者 (VIEWER)
        result = await conn.execute(
            select(User).where(User.email == "zhaoliu@abctech.com")
        )
        zhaoliu_user = result.scalar_one_or_none()
        
        if not zhaoliu_user:
            zhaoliu_id = str(uuid4())
            hashed_pw = bcrypt.hashpw("Zhaoliu123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                insert(User).values(
                    id=zhaoliu_id,
                    tenant_id=abc_tenant_id,
                    username="zhaoliu",
                    email="zhaoliu@abctech.com",
                    hashed_password=hashed_pw,
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建用户: zhaoliu@abctech.com / Zhaoliu123!@# (VIEWER)")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(User.id).where(User.email == "zhaoliu@abctech.com")
            )
            zhaoliu_id = result.scalar_one_or_none()
            print(f"ℹ️  用户已存在: zhaoliu@abctech.com")

        # ============ 3. 创建工作空间 ============
        
        # ABC科技 - 产品部工作空间
        result = await conn.execute(
            select(Workspace).where(
                Workspace.tenant_id == abc_tenant_id,
                Workspace.name == "产品部"
            )
        )
        product_workspace = result.scalar_one_or_none()
        
        if not product_workspace:
            product_ws_id = str(uuid4())
            await conn.execute(
                insert(Workspace).values(
                    id=product_ws_id,
                    tenant_id=abc_tenant_id,
                    name="产品部",
                    description="ABC科技产品部工作空间",
                    is_default=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建工作空间: 产品部")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(Workspace.id).where(
                    Workspace.tenant_id == abc_tenant_id,
                    Workspace.name == "产品部"
                )
            )
            product_ws_id = result.scalar_one_or_none()
            print(f"ℹ️  工作空间已存在: 产品部")

        # ABC科技 - 研发部工作空间
        result = await conn.execute(
            select(Workspace).where(
                Workspace.tenant_id == abc_tenant_id,
                Workspace.name == "研发部"
            )
        )
        dev_workspace = result.scalar_one_or_none()
        
        if not dev_workspace:
            dev_ws_id = str(uuid4())
            await conn.execute(
                insert(Workspace).values(
                    id=dev_ws_id,
                    tenant_id=abc_tenant_id,
                    name="研发部",
                    description="ABC科技研发部工作空间",
                    is_default=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 创建工作空间: 研发部")
        else:
            # 直接使用查询结果的id
            result = await conn.execute(
                select(Workspace.id).where(
                    Workspace.tenant_id == abc_tenant_id,
                    Workspace.name == "研发部"
                )
            )
            dev_ws_id = result.scalar_one_or_none()
            print(f"ℹ️  工作空间已存在: 研发部")

        # ============ 4. 添加工作空间成员 ============
        
        # 产品部成员
        members_to_add = [
            (zhangsan_id, "owner"),   # 张三: 产品部所有者
            (lisi_id, "admin"),       # 李四: 产品部管理员
            (wangwu_id, "member"),    # 王五: 产品部成员
            (zhaoliu_id, "viewer"),   # 赵六: 产品部查看者
        ]
        
        for user_id, role in members_to_add:
            result = await conn.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == product_ws_id,
                    WorkspaceMember.user_id == user_id
                )
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                await conn.execute(
                    insert(WorkspaceMember).values(
                        id=str(uuid4()),
                        workspace_id=product_ws_id,
                        user_id=user_id,
                        role=role,
                        joined_at=datetime.utcnow()
                    )
                )
                print(f"✅ 产品部添加成员: 用户ID={user_id[-8:]}, 角色={role}")
        
        # 研发部成员
        dev_members = [
            (lisi_id, "owner"),       # 李四: 研发部所有者
            (wangwu_id, "admin"),     # 王五: 研发部管理员
            (zhangsan_id, "viewer"),  # 张三: 研发部查看者
        ]
        
        for user_id, role in dev_members:
            result = await conn.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == dev_ws_id,
                    WorkspaceMember.user_id == user_id
                )
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                await conn.execute(
                    insert(WorkspaceMember).values(
                        id=str(uuid4()),
                        workspace_id=dev_ws_id,
                        user_id=user_id,
                        role=role,
                        joined_at=datetime.utcnow()
                    )
                )
                print(f"✅ 研发部添加成员: 用户ID={user_id[-8:]}, 角色={role}")

    print("\n" + "="*60)
    print("🎉 种子数据生成完成！")
    print("="*60)
    print("\n📋 测试账号列表:")
    print("-"*60)
    print("1. 超级管理员 (可管理所有租户):")
    print("   邮箱: superadmin@system.com")
    print("   密码: SuperAdmin123!@#")
    print()
    print("2. ABC科技公司 - 张三 (产品部 OWNER):")
    print("   邮箱: zhangsan@abctech.com")
    print("   密码: Zhangsan123!@#")
    print()
    print("3. ABC科技公司 - 李四 (产品部 ADMIN, 研发部 OWNER):")
    print("   邮箱: lisi@abctech.com")
    print("   密码: Lisi123!@#")
    print()
    print("4. ABC科技公司 - 王五 (产品部 MEMBER, 研发部 ADMIN):")
    print("   邮箱: wangwu@abctech.com")
    print("   密码: Wangwu123!@#")
    print()
    print("5. ABC科技公司 - 赵六 (产品部 VIEWER):")
    print("   邮箱: zhaoliu@abctech.com")
    print("   密码: Zhaoliu123!@#")
    print("-"*60)


if __name__ == "__main__":
    asyncio.run(seed_database())
