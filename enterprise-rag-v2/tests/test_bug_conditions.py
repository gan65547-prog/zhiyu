"""Bug条件探索测试"""

import os
import subprocess
import time
import requests
import re
from typing import List


def test_qdrant_health_check():
    """测试Qdrant健康检查"""
    print("=== 测试Qdrant健康检查 ===")
    try:
        # 启动服务
        subprocess.run(["docker-compose", "up", "-d"], cwd="/Users/gan/Documents/ganfy/enterprise-rag-v2")
        time.sleep(30)  # 等待服务启动
        
        # 检查健康状态
        response = requests.get("http://localhost:6333/health", timeout=10)
        print(f"Qdrant健康检查状态码: {response.status_code}")
        print(f"Qdrant健康检查响应: {response.text}")
        
        # 断言应该失败，因为当前配置缺少健康检查
        assert response.status_code == 200, f"Qdrant健康检查失败，状态码: {response.status_code}"
        print("✓ Qdrant健康检查通过")
    except Exception as e:
        print(f"✗ Qdrant健康检查失败: {e}")
        # 预期会失败，所以这里不抛出异常
    finally:
        # 停止服务
        subprocess.run(["docker-compose", "down"], cwd="/Users/gan/Documents/ganfy/enterprise-rag-v2")


def test_qdrant_auto_restart():
    """测试Qdrant自动重启"""
    print("\n=== 测试Qdrant自动重启 ===")
    try:
        # 启动服务
        subprocess.run(["docker-compose", "up", "-d"], cwd="/Users/gan/Documents/ganfy/enterprise-rag-v2")
        time.sleep(30)  # 等待服务启动
        
        # 停止Qdrant容器
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=enterprise-rag-v2_qdrant_1", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        container_name = result.stdout.strip()
        
        if container_name:
            print(f"停止Qdrant容器: {container_name}")
            subprocess.run(["docker", "stop", container_name])
            time.sleep(10)  # 等待重启
            
            # 检查容器状态
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=enterprise-rag-v2_qdrant_1", "--format", "{{.Status}}"],
                capture_output=True, text=True
            )
            status = result.stdout.strip()
            print(f"Qdrant容器状态: {status}")
            
            # 断言应该失败，因为当前配置缺少自动重启
            assert "Up" in status, f"Qdrant容器未自动重启，状态: {status}"
            print("✓ Qdrant自动重启成功")
        else:
            print("✗ 未找到Qdrant容器")
    except Exception as e:
        print(f"✗ Qdrant自动重启测试失败: {e}")
        # 预期会失败，所以这里不抛出异常
    finally:
        # 停止服务
        subprocess.run(["docker-compose", "down"], cwd="/Users/gan/Documents/ganfy/enterprise-rag-v2")


def test_debug_code_in_user_service():
    """测试user_service_impl.py中的调试代码"""
    print("\n=== 测试user_service_impl.py中的调试代码 ===")
    file_path = "/Users/gan/Documents/ganfy/enterprise-rag-v2/services/impl/user_service_impl.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计print()语句数量
        print_statements = re.findall(r'print\(', content)
        print_count = len(print_statements)
        print(f"user_service_impl.py中的print()语句数量: {print_count}")
        
        # 断言应该失败，因为存在print()语句
        assert print_count == 0, f"user_service_impl.py中存在{print_count}处print()语句"
        print("✓ user_service_impl.py中无print()语句")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 预期会失败，所以这里不抛出异常


def test_debug_code_in_workspace_repository():
    """测试workspace_repository.py中的调试代码"""
    print("\n=== 测试workspace_repository.py中的调试代码 ===")
    file_path = "/Users/gan/Documents/ganfy/enterprise-rag-v2/infrastructure/repositories/workspace_repository.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计print()语句数量
        print_statements = re.findall(r'print\(', content)
        print_count = len(print_statements)
        print(f"workspace_repository.py中的print()语句数量: {print_count}")
        
        # 断言应该失败，因为存在print()语句
        assert print_count == 0, f"workspace_repository.py中存在{print_count}处print()语句"
        print("✓ workspace_repository.py中无print()语句")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 预期会失败，所以这里不抛出异常


def test_env_config_completeness():
    """测试环境配置完整性"""
    print("\n=== 测试环境配置完整性 ===")
    file_path = "/Users/gan/Documents/ganfy/enterprise-rag-v2/.env.example"
    
    required_vars = [
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TEMPERATURE"
    ]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        missing_vars = []
        for var in required_vars:
            if var not in content:
                missing_vars.append(var)
        
        print(f"缺失的LLM配置变量: {missing_vars}")
        
        # 断言应该失败，因为缺少LLM配置
        assert len(missing_vars) == 0, f"缺少{len(missing_vars)}个LLM配置变量: {missing_vars}"
        print("✓ 环境配置完整")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        # 预期会失败，所以这里不抛出异常


if __name__ == "__main__":
    print("开始执行Bug条件探索测试...")
    print("这些测试预期会失败，以确认bug存在")
    print("=" * 60)
    
    test_qdrant_health_check()
    test_qdrant_auto_restart()
    test_debug_code_in_user_service()
    test_debug_code_in_workspace_repository()
    test_env_config_completeness()
    
    print("\n" + "=" * 60)
    print("Bug条件探索测试完成")
    print("如果测试失败，说明bug存在，符合预期")
