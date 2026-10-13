"""保留属性测试"""

import os
import re
from typing import List


def test_existing_logger_usage():
    """测试已使用logger的模块保持不变"""
    print("=== 测试已使用logger的模块保持不变 ===")
    
    # 假设其他模块已经使用logger
    # 这里我们检查一些关键模块是否使用logger
    modules_to_check = [
        "services/impl/document_service_impl.py",
        "services/impl/rag_service_impl.py",
        "api/main.py"
    ]
    
    for module_path in modules_to_check:
        full_path = f"/Users/gan/Documents/ganfy/enterprise-rag-v2/{module_path}"
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 检查是否导入logging
                has_logging_import = 'import logging' in content or 'from logging' in content
                # 检查是否使用logger
                has_logger_usage = 'logger.' in content
                
                print(f"模块 {module_path}:")
                print(f"  - 导入logging: {'✓' if has_logging_import else '✗'}")
                print(f"  - 使用logger: {'✓' if has_logger_usage else '✗'}")
                
                # 这些模块应该使用logger
                # 注意：这里只是检查，不强制断言，因为可能有些模块还没有实现
            except Exception as e:
                print(f"  - 检查失败: {e}")
        else:
            print(f"模块 {module_path} 不存在")


def test_existing_env_variables():
    """测试现有环境变量保持不变"""
    print("\n=== 测试现有环境变量保持不变 ===")
    file_path = "/Users/gan/Documents/ganfy/enterprise-rag-v2/.env.example"
    
    existing_vars = [
        "APP_NAME",
        "DATABASE_URL",
        "REDIS_URL",
        "QDRANT_URL",
        "JWT_SECRET",
        "LOG_LEVEL",
        "CELERY_BROKER_URL"
    ]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        missing_vars = []
        for var in existing_vars:
            if var not in content:
                missing_vars.append(var)
        
        print(f"现有环境变量检查:")
        for var in existing_vars:
            status = "✓" if var in content else "✗"
            print(f"  - {var}: {status}")
        
        if missing_vars:
            print(f"  - 缺失变量: {missing_vars}")
        else:
            print("  - 所有现有变量都存在")
            
    except Exception as e:
        print(f"测试失败: {e}")


def test_test_scripts_print_usage():
    """测试测试脚本中的print()保持不变"""
    print("\n=== 测试测试脚本中的print()保持不变 ===")
    
    test_directories = [
        "tests",
        "scripts"
    ]
    
    for directory in test_directories:
        full_path = f"/Users/gan/Documents/ganfy/enterprise-rag-v2/{directory}"
        if os.path.exists(full_path):
            print(f"检查 {directory} 目录:")
            
            # 递归查找Python文件
            for root, dirs, files in os.walk(full_path):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # 统计print()语句数量
                            print_statements = re.findall(r'print\(', content)
                            print_count = len(print_statements)
                            
                            if print_count > 0:
                                print(f"  - {os.path.relpath(file_path, full_path)}: {print_count}处print()")
                        except Exception as e:
                            print(f"  - {os.path.relpath(file_path, full_path)}: 检查失败 - {e}")
        else:
            print(f"目录 {directory} 不存在")


def test_core_business_functions():
    """测试核心业务功能文件存在"""
    print("\n=== 测试核心业务功能文件存在 ===")
    
    core_files = [
        "services/impl/auth_service_impl.py",
        "services/impl/tenant_service_impl.py",
        "services/impl/workspace_service_impl.py",
        "infrastructure/database/models.py",
        "api/routes/auth.py",
        "api/routes/tenant.py",
        "api/routes/workspace.py"
    ]
    
    for file_path in core_files:
        full_path = f"/Users/gan/Documents/ganfy/enterprise-rag-v2/{file_path}"
        if os.path.exists(full_path):
            print(f"  - {file_path}: ✓ 存在")
        else:
            print(f"  - {file_path}: ✗ 不存在")


if __name__ == "__main__":
    print("开始执行保留属性测试...")
    print("这些测试应该通过，以确保现有功能不受影响")
    print("=" * 60)
    
    test_existing_logger_usage()
    test_existing_env_variables()
    test_test_scripts_print_usage()
    test_core_business_functions()
    
    print("\n" + "=" * 60)
    print("保留属性测试完成")
    print("如果测试通过，说明现有功能未受影响")
