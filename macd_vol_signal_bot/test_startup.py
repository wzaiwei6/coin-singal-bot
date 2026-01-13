#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动测试 - 验证主程序能否正常初始化
"""
import sys
import os

# 切换到项目目录
os.chdir('/Users/wang/PythonProjects/coin-singal-bot/macd_vol_signal_bot')

print("🧪 测试主程序初始化...\n")

try:
    # 测试所有导入
    from market.binance import build_exchange, fetch_klines
    from strategy.macd_vol import generate_signal
    from dedup.dedup import DedupManager
    from notifier.wecom import send_signal, send_startup_notification
    from llm.analyzer import analyze_signal
    import yaml
    
    print("✅ 所有模块导入成功")
    
    # 测试配置加载
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print("✅ 配置文件加载成功")
    print(f"   监控币种: {', '.join(config.get('symbols', []))}")
    print(f"   监控周期: {', '.join(config.get('timeframes', []))}")
    
    # 测试去重管理器初始化
    dedup_mgr = DedupManager('.test_state.json', 120)
    print("✅ 去重管理器初始化成功")
    
    # 清理测试文件
    if os.path.exists('.test_state.json'):
        os.remove('.test_state.json')
    
    print("\n" + "="*60)
    print("✅ 主程序所有组件初始化测试通过！")
    print("="*60)
    print("\n💡 现在可以运行 'python main.py' 启动机器人了！\n")
    
except Exception as e:
    print(f"\n❌ 初始化测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
