#!/bin/bash
# MACD V2 调试模式启动脚本

# 激活虚拟环境
source /Users/wang/PythonProjects/.venv/bin/activate

# 设置调试模式
export MACD_DEBUG=true

# 运行脚本
python macd_signal_bot_v2.py

