#!/bin/bash
# 插针策略一键启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查 Python 环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ 未找到 Python3，请先安装 Python${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Python 版本:${NC} $(python3 --version)"
}

# 检查依赖包
check_dependencies() {
    echo -e "${BLUE}🔍 检查依赖包...${NC}"
    
    python3 -c "import pandas, numpy" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}⚠️  缺少依赖包，正在安装...${NC}"
        pip3 install pandas numpy matplotlib
    else
        echo -e "${GREEN}✅ 依赖包已安装${NC}"
    fi
}

# 显示菜单
show_menu() {
    clear
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                🎯 插针反弹策略系统${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}请选择操作：${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC} - 🧪 快速测试（5个币种，验证逻辑）"
    echo -e "  ${GREEN}2${NC} - 🔍 插针信号检测（查看BTC插针信号）"
    echo -e "  ${GREEN}3${NC} - 🔧 参数优化（找最优参数）"
    echo -e "  ${GREEN}4${NC} - 🚀 完整回测（所有币种）"
    echo -e "  ${GREEN}5${NC} - 📊 生成图表（需要先有回测结果）"
    echo -e "  ${GREEN}6${NC} - 📖 查看文档"
    echo -e "  ${GREEN}7${NC} - ⚙️  编辑配置"
    echo -e "  ${GREEN}0${NC} - 🚪 退出"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# 快速测试
quick_test() {
    echo -e "${GREEN}🧪 开始快速测试...${NC}"
    echo ""
    echo -e "${YELLOW}将测试 BTC、ETH、SOL、DOGE、BNB 五个币种${NC}"
    echo ""
    read -p "按回车继续..." dummy
    
    python3 spike_strategy_quick_test.py <<< "1"
    
    echo ""
    echo -e "${GREEN}✅ 测试完成！${NC}"
    read -p "按回车返回菜单..." dummy
}

# 插针信号检测
spike_detection() {
    echo -e "${GREEN}🔍 检测 BTC 插针信号...${NC}"
    echo ""
    read -p "按回车继续..." dummy
    
    python3 spike_strategy_quick_test.py <<< "2"
    
    echo ""
    echo -e "${GREEN}✅ 检测完成！${NC}"
    read -p "按回车返回菜单..." dummy
}

# 参数优化
optimize() {
    echo -e "${GREEN}🔧 开始参数优化...${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  警告：这可能需要 10-30 分钟${NC}"
    echo ""
    read -p "确认继续？(y/n): " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        python3 spike_strategy_optimizer.py
        
        echo ""
        echo -e "${GREEN}✅ 优化完成！${NC}"
        echo -e "${BLUE}💡 下一步：${NC}"
        echo "   1. 查看 backtest_results/spike_strategy/ 下的优化结果"
        echo "   2. 将最优参数更新到 spike_strategy_config.py"
        echo "   3. 运行完整回测"
    else
        echo -e "${YELLOW}⏭️  已取消${NC}"
    fi
    
    echo ""
    read -p "按回车返回菜单..." dummy
}

# 完整回测
full_backtest() {
    echo -e "${GREEN}🚀 开始完整回测...${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  警告：这可能需要 5-30 分钟（取决于币种数量）${NC}"
    echo ""
    read -p "确认继续？(y/n): " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        python3 spike_strategy_backtest.py
        
        echo ""
        echo -e "${GREEN}✅ 回测完成！${NC}"
        echo -e "${BLUE}💡 下一步：${NC}"
        echo "   1. 查看终端输出的回测报告"
        echo "   2. 运行【生成图表】查看可视化结果"
        echo "   3. 查看 backtest_results/spike_strategy/ 下的交易明细"
    else
        echo -e "${YELLOW}⏭️  已取消${NC}"
    fi
    
    echo ""
    read -p "按回车返回菜单..." dummy
}

# 生成图表
generate_charts() {
    echo -e "${GREEN}📊 生成图表...${NC}"
    echo ""
    
    # 查找最新的回测结果文件
    LATEST_FILE=$(ls -t backtest_results/spike_strategy/插针反弹策略*.csv 2>/dev/null | head -1)
    
    if [ -z "$LATEST_FILE" ]; then
        echo -e "${RED}❌ 未找到回测结果文件${NC}"
        echo -e "${YELLOW}💡 请先运行【完整回测】或【快速测试】${NC}"
    else
        echo -e "${BLUE}📂 使用文件: ${LATEST_FILE}${NC}"
        echo ""
        python3 spike_strategy_visualize.py "$LATEST_FILE"
        
        echo ""
        echo -e "${GREEN}✅ 图表生成完成！${NC}"
        echo -e "${BLUE}📂 查看图表：backtest_results/spike_strategy/plots_*/${NC}"
    fi
    
    echo ""
    read -p "按回车返回菜单..." dummy
}

# 查看文档
view_docs() {
    clear
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                📖 文档列表${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "1. SPIKE_STRATEGY_GUIDE.md      - 快速使用指南"
    echo "2. spike_strategy_README.md     - 详细策略说明"
    echo "3. 插针策略设计总结.md           - 完整设计文档"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    read -p "输入文档编号查看 (1/2/3) 或按回车返回: " doc_choice
    
    case $doc_choice in
        1)
            less SPIKE_STRATEGY_GUIDE.md 2>/dev/null || cat SPIKE_STRATEGY_GUIDE.md
            ;;
        2)
            less spike_strategy_README.md 2>/dev/null || cat spike_strategy_README.md
            ;;
        3)
            less 插针策略设计总结.md 2>/dev/null || cat 插针策略设计总结.md
            ;;
        *)
            return
            ;;
    esac
    
    echo ""
    read -p "按回车返回菜单..." dummy
}

# 编辑配置
edit_config() {
    echo -e "${GREEN}⚙️  编辑配置文件...${NC}"
    echo ""
    
    if command -v nano &> /dev/null; then
        nano spike_strategy_config.py
    elif command -v vim &> /dev/null; then
        vim spike_strategy_config.py
    else
        echo -e "${YELLOW}⚠️  未找到文本编辑器，请手动编辑：${NC}"
        echo "   spike_strategy_config.py"
    fi
    
    echo ""
    read -p "按回车返回菜单..." dummy
}

# 主程序
main() {
    # 切换到脚本所在目录
    cd "$(dirname "$0")" || exit
    
    # 检查环境
    check_python
    check_dependencies
    
    echo ""
    read -p "按回车进入主菜单..." dummy
    
    # 主循环
    while true; do
        show_menu
        read -p "请输入选项 (0-7): " choice
        
        case $choice in
            1)
                quick_test
                ;;
            2)
                spike_detection
                ;;
            3)
                optimize
                ;;
            4)
                full_backtest
                ;;
            5)
                generate_charts
                ;;
            6)
                view_docs
                ;;
            7)
                edit_config
                ;;
            0)
                echo ""
                echo -e "${GREEN}👋 再见！祝交易顺利！${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo ""
                echo -e "${RED}❌ 无效的选项，请重新输入${NC}"
                sleep 2
                ;;
        esac
    done
}

# 运行主程序
main

