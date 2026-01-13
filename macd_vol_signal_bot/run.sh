#!/bin/bash
# MACD 波动率信号机器人启动脚本

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo "  MACD 波动率信号机器人 - 启动脚本"
echo "============================================================"
echo ""

# 检查虚拟环境
if [ ! -d "../venv" ]; then
    echo -e "${YELLOW}⚠️  未找到虚拟环境，正在创建...${NC}"
    cd ..
    python3 -m venv venv
    cd "$SCRIPT_DIR"
fi

# 激活虚拟环境
echo -e "${GREEN}✅ 激活虚拟环境...${NC}"
source ../venv/bin/activate

# 检查依赖
echo -e "${GREEN}✅ 检查依赖...${NC}"
pip install -r requirements.txt -q

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}❌ 未找到配置文件 config.yaml${NC}"
    exit 1
fi

# 运行程序
echo ""
echo -e "${GREEN}🚀 启动机器人...${NC}"
echo ""
python main.py
