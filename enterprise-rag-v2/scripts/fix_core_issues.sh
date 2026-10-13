#!/bin/bash

# 核心业务流程修复脚本

echo "=========================================="
echo "核心业务流程修复脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查并启动Qdrant服务
echo "1. 检查Qdrant服务..."
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Qdrant服务已运行${NC}"
else
    echo -e "${YELLOW}⚠ Qdrant服务未运行，尝试启动...${NC}"
    
    # 检查Docker是否运行
    if docker info > /dev/null 2>&1; then
        echo "  启动Qdrant容器..."
        docker run -d -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant
        
        # 等待服务启动
        echo "  等待服务启动..."
        sleep 5
        
        if curl -s http://localhost:6333/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Qdrant服务启动成功${NC}"
        else
            echo -e "${RED}✗ Qdrant服务启动失败${NC}"
            echo "  请手动启动: docker run -d -p 6333:6333 qdrant/qdrant"
        fi
    else
        echo -e "${RED}✗ Docker未运行，无法启动Qdrant${NC}"
        echo "  请先启动Docker，然后运行:"
        echo "  docker run -d -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant"
    fi
fi

echo ""

# 2. 检查.env配置
echo "2. 检查.env配置..."

if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env文件不存在${NC}"
    echo "  复制.env.example到.env并配置"
    exit 1
fi

# 检查关键配置
check_env_var() {
    local var_name=$1
    if grep -q "^${var_name}=" .env && ! grep -q "^${var_name}=$" .env; then
        echo -e "${GREEN}✓ ${var_name} 已配置${NC}"
        return 0
    else
        echo -e "${RED}✗ ${var_name} 未配置${NC}"
        return 1
    fi
}

check_env_var "DATABASE_URL"
check_env_var "QDRANT_URL"
check_env_var "LLM_PROVIDER"
check_env_var "OPENAI_API_KEY"

echo ""

# 3. 检查数据库
echo "3. 检查数据库..."

if [ -f "enterprise_rag.db" ] || [ -f "knowledge_base.db" ]; then
    echo -e "${GREEN}✓ 数据库文件存在${NC}"
else
    echo -e "${YELLOW}⚠ 数据库文件不存在，需要初始化${NC}"
    echo "  运行: python scripts/init_db.py"
fi

echo ""

# 4. 检查Python依赖
echo "4. 检查Python依赖..."

if [ -d ".venv" ] || [ -d "venv" ]; then
    echo -e "${GREEN}✓ 虚拟环境存在${NC}"
    
    # 激活虚拟环境并检查关键包
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        source venv/bin/activate
    fi
    
    # 检查关键包
    python3 -c "import fastapi" 2>/dev/null && echo -e "${GREEN}✓ fastapi 已安装${NC}" || echo -e "${YELLOW}⚠ fastapi 未安装${NC}"
    python3 -c "import qdrant_client" 2>/dev/null && echo -e "${GREEN}✓ qdrant-client 已安装${NC}" || echo -e "${YELLOW}⚠ qdrant-client 未安装${NC}"
    python3 -c "import sqlalchemy" 2>/dev/null && echo -e "${GREEN}✓ sqlalchemy 已安装${NC}" || echo -e "${YELLOW}⚠ sqlalchemy 未安装${NC}"
    
else
    echo -e "${YELLOW}⚠ 虚拟环境不存在${NC}"
    echo "  创建虚拟环境: python3 -m venv .venv"
    echo "  激活虚拟环境: source .venv/bin/activate"
    echo "  安装依赖: pip install -r requirements.txt"
fi

echo ""

# 5. 运行诊断脚本
echo "5. 运行系统诊断..."
python3 scripts/diagnose_system.py

echo ""
echo "=========================================="
echo "修复脚本执行完成"
echo "=========================================="
echo ""
echo "下一步:"
echo "  1. 确保Qdrant服务正在运行"
echo "  2. 检查.env配置是否完整"
echo "  3. 运行API服务: uvicorn main:app --reload"
echo "  4. 测试核心业务流程"
