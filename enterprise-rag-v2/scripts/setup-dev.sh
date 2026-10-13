#!/bin/bash

# 企业级RAG系统V2 - 开发环境设置脚本

set -e

echo "🚀 开始设置企业级RAG系统V2开发环境..."

# 检查Python版本
echo "🔍 检查Python版本..."
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$python_version" < "3.10" ]]; then
    echo "❌ 需要Python 3.10或更高版本，当前版本: $python_version"
    exit 1
fi
echo "✅ Python版本: $python_version"

# 创建虚拟环境
echo "🔧 创建虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功"
else
    echo "⚠️  虚拟环境已存在，跳过创建"
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "📦 升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📦 安装项目依赖..."
pip install -r requirements.txt

# 安装开发依赖
echo "📦 安装开发依赖..."
pip install pytest pytest-asyncio pytest-cov black isort flake8 mypy

# 创建环境文件
echo "⚙️  创建环境配置文件..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ 环境文件创建成功"
    echo "⚠️  请编辑 .env 文件配置数据库连接和其他设置"
else
    echo "⚠️  .env文件已存在，跳过创建"
fi

# 创建日志目录
echo "📝 创建日志目录..."
mkdir -p logs

# 启动Docker服务
echo "🐳 启动Docker服务..."
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.dev.yml up -d
    echo "✅ Docker服务启动成功"
    
    # 等待服务就绪
    echo "⏳ 等待服务就绪..."
    sleep 10
else
    echo "⚠️  docker-compose未安装，跳过Docker服务启动"
    echo "⚠️  请手动启动数据库服务:"
    echo "    docker-compose -f docker-compose.dev.yml up -d"
fi

# 运行数据库迁移
echo "🗄️  运行数据库迁移..."
if [ -f "venv/bin/alembic" ]; then
    alembic upgrade head
    echo "✅ 数据库迁移完成"
else
    echo "⚠️  alembic未安装，跳过数据库迁移"
fi

# 创建测试数据
echo "📊 创建测试数据..."
if [ -f "scripts/create_test_data.py" ]; then
    python scripts/create_test_data.py
    echo "✅ 测试数据创建完成"
else
    echo "⚠️  测试数据脚本不存在，跳过"
fi

echo ""
echo "🎉 开发环境设置完成！"
echo ""
echo "📋 下一步操作:"
echo "1. 启动应用: python main.py"
echo "2. 访问API文档: http://localhost:8000/api/docs"
echo "3. 运行测试: pytest"
echo ""
echo "🔧 开发命令:"
echo "  • 启动应用: python main.py"
echo "  • 运行测试: pytest"
echo "  • 代码格式化: black . && isort ."
echo "  • 代码检查: flake8 . && mypy ."
echo "  • 重启Docker服务: docker-compose -f docker-compose.dev.yml restart"
echo ""
echo "📚 文档:"
echo "  • 架构设计: docs/ARCHITECTURE_COMPLETION_REPORT.md"
echo "  • API接口: docs/API_INTERFACE_DEFINITION.md"
echo "  • 开发指南: docs/DEVELOPMENT_GUIDE.md"