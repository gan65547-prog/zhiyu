#!/usr/bin/env python3
"""
系统诊断脚本 - 检查核心业务流程的关键组件

不依赖完整的服务层，直接检查核心组件
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


async def check_environment():
    """检查环境配置"""
    print_header("1. 环境配置检查")
    
    issues = []
    
    # 检查.env文件
    env_file = Path(".env")
    if env_file.exists():
        print_success(".env 文件存在")
        
        # 读取并检查关键配置
        with open(env_file) as f:
            env_content = f.read()
            
        required_vars = [
            "DATABASE_URL",
            "QDRANT_URL",
            "LLM_PROVIDER",
            "OPENAI_API_KEY"
        ]
        
        for var in required_vars:
            if var in env_content and not env_content.split(var)[1].split('\n')[0].strip() == '=':
                print_success(f"  {var} 已配置")
            else:
                print_error(f"  {var} 未配置或为空")
                issues.append(f"缺少配置: {var}")
    else:
        print_error(".env 文件不存在")
        issues.append("缺少.env文件")
    
    return len(issues) == 0, issues


async def check_qdrant():
    """检查Qdrant服务"""
    print_header("2. Qdrant向量数据库检查")
    
    try:
        import httpx
        
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        print_info(f"Qdrant URL: {qdrant_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{qdrant_url}/health", timeout=5.0)
            
            if response.status_code == 200:
                print_success("Qdrant服务运行正常")
                
                # 获取集合列表
                collections_response = await client.get(f"{qdrant_url}/collections")
                if collections_response.status_code == 200:
                    collections = collections_response.json().get('result', {}).get('collections', [])
                    print_success(f"找到 {len(collections)} 个向量集合")
                    
                    if collections:
                        print_info("现有集合:")
                        for col in collections[:5]:  # 只显示前5个
                            name = col.get('name', 'unknown')
                            print(f"    - {name}")
                    
                return True, None
            else:
                print_error(f"Qdrant服务响应异常: {response.status_code}")
                return False, "Qdrant服务不可用"
                
    except Exception as e:
        print_error(f"无法连接到Qdrant: {e}")
        print_warning("请确保Qdrant服务正在运行:")
        print_warning("  docker run -p 6333:6333 qdrant/qdrant")
        return False, str(e)


async def check_database():
    """检查数据库"""
    print_header("3. 数据库检查")
    
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import NullPool
        
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./enterprise_rag.db")
        
        # 转换为同步URL用于检查
        sync_url = db_url.replace("+aiosqlite", "").replace("postgresql+asyncpg", "postgresql")
        print_info(f"数据库 URL: {sync_url}")
        
        engine = create_engine(sync_url, poolclass=NullPool)
        
        with engine.connect() as conn:
            # 检查表是否存在
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'" 
                if 'sqlite' in sync_url 
                else "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            ))
            
            tables = [row[0] for row in result]
            print_success(f"数据库连接正常，找到 {len(tables)} 个表")
            
            if tables:
                print_info("核心表:")
                core_tables = ['users', 'workspaces', 'datasets', 'documents', 'conversations']
                for table in core_tables:
                    if table in tables:
                        print_success(f"  ✓ {table}")
                    else:
                        print_warning(f"  ✗ {table} (缺失)")
                
                # 检查数据
                if 'users' in tables:
                    result = conn.execute(text("SELECT COUNT(*) FROM users"))
                    user_count = result.scalar()
                    print_info(f"\n用户数量: {user_count}")
                    
                if 'datasets' in tables:
                    result = conn.execute(text("SELECT COUNT(*) FROM datasets"))
                    dataset_count = result.scalar()
                    print_info(f"数据集数量: {dataset_count}")
                    
                if 'documents' in tables:
                    result = conn.execute(text("SELECT COUNT(*) FROM documents"))
                    doc_count = result.scalar()
                    print_info(f"文档数量: {doc_count}")
            
            return True, None
            
    except Exception as e:
        print_error(f"数据库检查失败: {e}")
        return False, str(e)


async def check_llm_provider():
    """检查LLM提供商配置"""
    print_header("4. LLM提供商检查")
    
    llm_provider = os.getenv("LLM_PROVIDER", "")
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if not llm_provider:
        print_error("LLM_PROVIDER 未配置")
        return False, "LLM_PROVIDER未配置"
    
    print_success(f"LLM提供商: {llm_provider}")
    
    if llm_provider == "openai":
        if api_key and api_key != "your-api-key-here":
            print_success("OpenAI API Key 已配置")
            print_info(f"API Key: {api_key[:10]}...{api_key[-4:]}")
            return True, None
        else:
            print_error("OpenAI API Key 未配置或无效")
            return False, "API Key未配置"
    
    return True, None


async def check_file_structure():
    """检查文件结构"""
    print_header("5. 项目文件结构检查")
    
    required_dirs = [
        "api",
        "core",
        "services",
        "infrastructure",
        "uploads"
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print_success(f"  ✓ {dir_name}/")
        else:
            print_error(f"  ✗ {dir_name}/ (缺失)")
            all_exist = False
    
    # 检查关键文件
    key_files = [
        "main.py",
        "requirements.txt",
        ".env.example"
    ]
    
    for file_name in key_files:
        file_path = Path(file_name)
        if file_path.exists():
            print_success(f"  ✓ {file_name}")
        else:
            print_warning(f"  ✗ {file_name} (缺失)")
    
    return all_exist, None if all_exist else "部分目录缺失"


async def check_vector_collection_naming():
    """检查向量集合命名一致性"""
    print_header("6. 向量集合命名检查")
    
    try:
        # 检查代码中的集合命名逻辑
        issues = []
        
        # 检查document_service.py
        doc_service_path = Path("services/impl/document_service.py")
        if doc_service_path.exists():
            with open(doc_service_path) as f:
                content = f.read()
                
            if 'f"dataset_{' in content:
                print_success("document_service.py 使用 dataset_{id} 命名")
            else:
                print_warning("document_service.py 集合命名可能不一致")
                issues.append("document_service.py命名不一致")
        
        # 检查chat_service.py
        chat_service_path = Path("services/impl/chat_service.py")
        if chat_service_path.exists():
            with open(chat_service_path) as f:
                content = f.read()
                
            if 'f"dataset_{' in content or 'collection_name' in content:
                print_success("chat_service.py 包含集合命名逻辑")
            else:
                print_error("chat_service.py 可能缺少集合命名逻辑")
                issues.append("chat_service.py缺少集合命名")
        
        if not issues:
            print_success("向量集合命名逻辑一致")
            return True, None
        else:
            return False, "集合命名不一致"
            
    except Exception as e:
        print_error(f"检查失败: {e}")
        return False, str(e)


async def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}系统诊断 - 核心业务流程检查{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    results = []
    
    # 执行所有检查
    checks = [
        ("环境配置", check_environment()),
        ("Qdrant服务", check_qdrant()),
        ("数据库", check_database()),
        ("LLM提供商", check_llm_provider()),
        ("文件结构", check_file_structure()),
        ("向量集合命名", check_vector_collection_naming())
    ]
    
    for name, check_coro in checks:
        passed, error = await check_coro
        results.append((name, passed, error))
    
    # 总结
    print_header("诊断总结")
    
    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)
    
    for name, passed, error in results:
        if passed:
            print_success(f"{name}: 正常")
        else:
            print_error(f"{name}: 异常 - {error}")
    
    print(f"\n{Colors.BOLD}通过率: {passed_count}/{total_count}{Colors.END}")
    
    if passed_count == total_count:
        print_success("\n✓ 所有检查通过！系统配置正常。")
        print_info("\n建议:")
        print_info("  1. 运行完整的端到端测试")
        print_info("  2. 测试文档上传和向量化")
        print_info("  3. 测试RAG对话功能")
        return 0
    else:
        print_error(f"\n✗ {total_count - passed_count} 项检查失败")
        print_warning("\n需要修复的问题:")
        for name, passed, error in results:
            if not passed:
                print(f"  - {name}: {error}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
