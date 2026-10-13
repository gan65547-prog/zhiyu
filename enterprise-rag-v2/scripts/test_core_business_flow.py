#!/usr/bin/env python3
"""
核心业务流程测试脚本

测试以下核心流程：
1. 文档上传和向量化
2. RAG对话查询
3. 向量存储集合管理
4. 数据集删除

使用方法:
    python scripts/test_core_business_flow.py
"""

import asyncio
import sys
import os
from pathlib import Path
from uuid import UUID
import tempfile

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.database.session import get_db_context
from infrastructure.database.models import User, Workspace, Dataset, Document
from services.impl.auth_service import AuthServiceImpl
from services.impl.dataset_service import DatasetServiceImpl
from services.impl.document_service import DocumentServiceImpl
from services.impl.chat_service import ChatServiceImpl
from core.rag.vector_store import QdrantVectorStore
from core.rag.embedding import EmbeddingService


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """打印错误信息"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    """打印警告信息"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text: str):
    """打印信息"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


async def check_environment():
    """检查环境配置"""
    print_header("环境配置检查")
    
    issues = []
    
    # 检查环境变量
    required_env_vars = [
        "DATABASE_URL",
        "QDRANT_URL",
        "LLM_PROVIDER",
        "OPENAI_API_KEY"
    ]
    
    for var in required_env_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var} 已配置")
        else:
            print_error(f"{var} 未配置")
            issues.append(f"缺少环境变量: {var}")
    
    # 检查Qdrant连接
    try:
        embedding_service = EmbeddingService()
        vector_store = QdrantVectorStore(
            collection_name="test_connection",
            embedding_service=embedding_service
        )
        # 尝试连接
        print_success("Qdrant服务连接正常")
    except Exception as e:
        print_error(f"Qdrant服务连接失败: {e}")
        issues.append("Qdrant服务不可用")
    
    # 检查数据库
    try:
        async with get_db_context() as session:
            # 简单查询测试
            result = await session.execute("SELECT 1")
            print_success("数据库连接正常")
    except Exception as e:
        print_error(f"数据库连接失败: {e}")
        issues.append("数据库不可用")
    
    if issues:
        print_warning(f"\n发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    print_success("\n环境配置检查通过")
    return True


async def test_document_upload_and_vectorization():
    """测试1: 文档上传和向量化"""
    print_header("测试1: 文档上传和向量化")
    
    try:
        async with get_db_context() as session:
            # 获取测试用户和工作空间
            user = await session.execute(
                "SELECT * FROM users LIMIT 1"
            )
            user = user.first()
            
            if not user:
                print_error("没有找到测试用户，请先创建用户")
                return False
            
            user_id = user[0]  # id字段
            print_info(f"使用用户ID: {user_id}")
            
            # 获取工作空间
            workspace = await session.execute(
                f"SELECT * FROM workspaces WHERE id IN "
                f"(SELECT workspace_id FROM memberships WHERE user_id = '{user_id}') LIMIT 1"
            )
            workspace = workspace.first()
            
            if not workspace:
                print_error("没有找到工作空间")
                return False
            
            workspace_id = workspace[0]
            print_info(f"使用工作空间ID: {workspace_id}")
            
            # 创建测试数据集
            dataset_service = DatasetServiceImpl(session)
            dataset = await dataset_service.create_dataset(
                name="测试数据集_核心流程",
                description="用于测试核心业务流程",
                workspace_id=UUID(workspace_id),
                user_id=UUID(user_id)
            )
            print_success(f"创建测试数据集: {dataset.id}")
            
            # 创建测试文档
            test_content = """
            # RAG系统介绍
            
            RAG（Retrieval-Augmented Generation）是一种结合检索和生成的AI技术。
            它通过检索相关文档来增强大语言模型的回答能力。
            
            ## 核心组件
            
            1. 文档处理器：负责解析和分块文档
            2. 向量化服务：将文本转换为向量表示
            3. 向量存储：存储和检索文档向量
            4. LLM提供商：生成最终答案
            
            ## 工作流程
            
            1. 用户提问
            2. 向量检索相关文档
            3. LLM基于检索结果生成答案
            """
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(test_content)
                temp_file_path = f.name
            
            try:
                # 上传文档
                document_service = DocumentServiceImpl(session)
                document = await document_service.upload_document(
                    dataset_id=dataset.id,
                    file_path=temp_file_path,
                    filename="test_rag_intro.md",
                    user_id=UUID(user_id)
                )
                print_success(f"上传文档: {document.id}")
                
                # 处理文档
                print_info("开始处理文档...")
                success = await document_service.process_document(document.id)
                
                if success:
                    print_success("文档处理成功")
                    
                    # 验证向量存储
                    collection_name = f"dataset_{str(dataset.id)}"
                    embedding_service = EmbeddingService()
                    vector_store = QdrantVectorStore(
                        collection_name=collection_name,
                        embedding_service=embedding_service
                    )
                    
                    # 检查集合是否存在
                    if await vector_store.collection_exists():
                        print_success(f"向量集合已创建: {collection_name}")
                        
                        # 获取集合信息
                        info = await vector_store.get_collection_info()
                        vector_count = info.get('vectors_count', 0)
                        print_success(f"向量数量: {vector_count}")
                        
                        if vector_count > 0:
                            print_success("✓ 测试1通过: 文档上传和向量化正常")
                            return True, dataset.id
                        else:
                            print_error("向量数量为0")
                            return False, None
                    else:
                        print_error(f"向量集合不存在: {collection_name}")
                        return False, None
                else:
                    print_error("文档处理失败")
                    return False, None
                    
            finally:
                # 清理临时文件
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
    except Exception as e:
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_rag_chat(dataset_id: UUID):
    """测试2: RAG对话查询"""
    print_header("测试2: RAG对话查询")
    
    try:
        async with get_db_context() as session:
            # 获取测试用户
            user = await session.execute(
                "SELECT * FROM users LIMIT 1"
            )
            user = user.first()
            user_id = user[0]
            
            # 获取工作空间
            workspace = await session.execute(
                f"SELECT * FROM workspaces WHERE id IN "
                f"(SELECT workspace_id FROM memberships WHERE user_id = '{user_id}') LIMIT 1"
            )
            workspace = workspace.first()
            workspace_id = workspace[0]
            
            # 执行对话
            chat_service = ChatServiceImpl(session)
            
            test_query = "什么是RAG系统？"
            print_info(f"测试问题: {test_query}")
            
            response = await chat_service.chat(
                dataset_id=dataset_id,
                query=test_query,
                workspace_id=str(workspace_id),
                user_id=UUID(user_id),
                retrieval_mode="hybrid",
                top_k=5
            )
            
            # 验证响应
            if response.get('answer'):
                print_success(f"获得回答: {response['answer'][:100]}...")
                
                if response.get('sources'):
                    print_success(f"检索到 {len(response['sources'])} 个相关文档")
                    
                    # 显示来源
                    for i, source in enumerate(response['sources'][:3], 1):
                        score = source.get('score', 0)
                        content = source.get('content', '')[:50]
                        print_info(f"  来源{i}: 相似度={score:.3f}, 内容={content}...")
                    
                    print_success("✓ 测试2通过: RAG对话查询正常")
                    return True
                else:
                    print_warning("未检索到相关文档")
                    return False
            else:
                print_error("未获得回答")
                return False
                
    except Exception as e:
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_dataset_deletion(dataset_id: UUID):
    """测试3: 数据集删除"""
    print_header("测试3: 数据集删除")
    
    try:
        async with get_db_context() as session:
            # 获取测试用户
            user = await session.execute(
                "SELECT * FROM users LIMIT 1"
            )
            user = user.first()
            user_id = user[0]
            
            # 删除数据集
            dataset_service = DatasetServiceImpl(session)
            
            # 验证向量集合存在
            collection_name = f"dataset_{str(dataset_id)}"
            embedding_service = EmbeddingService()
            vector_store = QdrantVectorStore(
                collection_name=collection_name,
                embedding_service=embedding_service
            )
            
            exists_before = await vector_store.collection_exists()
            print_info(f"删除前向量集合存在: {exists_before}")
            
            # 执行删除
            await dataset_service.delete_dataset(
                dataset_id=dataset_id,
                user_id=UUID(user_id)
            )
            print_success("数据集删除成功")
            
            # 验证向量集合已删除
            exists_after = await vector_store.collection_exists()
            print_info(f"删除后向量集合存在: {exists_after}")
            
            if not exists_after:
                print_success("✓ 测试3通过: 数据集删除正常（包括向量数据）")
                return True
            else:
                print_warning("向量集合未删除")
                return False
                
    except Exception as e:
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print(f"\n{Colors.BOLD}核心业务流程测试{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
    
    # 检查环境
    if not await check_environment():
        print_error("\n环境检查失败，请修复问题后重试")
        return 1
    
    # 测试1: 文档上传和向量化
    test1_passed, dataset_id = await test_document_upload_and_vectorization()
    
    if not test1_passed:
        print_error("\n测试1失败，停止后续测试")
        return 1
    
    # 测试2: RAG对话查询
    test2_passed = await test_rag_chat(dataset_id)
    
    if not test2_passed:
        print_error("\n测试2失败")
        # 继续执行清理
    
    # 测试3: 数据集删除
    test3_passed = await test_dataset_deletion(dataset_id)
    
    # 总结
    print_header("测试总结")
    
    results = [
        ("文档上传和向量化", test1_passed),
        ("RAG对话查询", test2_passed),
        ("数据集删除", test3_passed)
    ]
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        if passed:
            print_success(f"{name}: 通过")
        else:
            print_error(f"{name}: 失败")
    
    print(f"\n{Colors.BOLD}通过率: {passed_count}/{total_count}{Colors.END}")
    
    if passed_count == total_count:
        print_success("\n所有测试通过！核心业务流程正常运行。")
        return 0
    else:
        print_error(f"\n{total_count - passed_count} 个测试失败，需要修复。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
