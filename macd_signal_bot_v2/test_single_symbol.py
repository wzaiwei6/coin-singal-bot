#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单个交易对测试脚本 - 用于调试
"""
import os
import sys

# 设置调试模式
os.environ['MACD_DEBUG'] = 'true'

# 导入主程序
from macd_signal_bot_v2 import (
    build_exchange, 
    check_symbol_signal,
    DEBUG_MODE
)

def main():
    """测试单个交易对"""
    symbol = "GRASS/USDT"
    
    print(f"🔍 测试交易对: {symbol}")
    print(f"🐛 调试模式: {DEBUG_MODE}")
    print("=" * 80)
    
    try:
        # 构建交易所
        exchange = build_exchange()
        
        # 检查信号（带调试信息）
        result = check_symbol_signal(exchange, symbol, debug=True)
        
        if result:
            print("\n" + "=" * 80)
            print("✅ 检测到信号！")
            print("=" * 80)
            print(f"方向: {result['direction']}")
            print(f"\n1h 触发数据:")
            print(f"  hist: {result['trigger']['hist']:.8f}")
            print(f"  delta: {result['trigger']['delta']:.8f}")
            print(f"  dif: {result['trigger']['dif']:.8f}")
            print(f"  dea: {result['trigger']['dea']:.8f}")
            
            print(f"\n共振数据:")
            for tf in ["15m", "5m", "3m"]:
                if tf in result['resonance']:
                    r = result['resonance'][tf]
                    print(f"  {tf}:")
                    print(f"    hist: {r['hist']:.8f}")
                    print(f"    delta: {r['delta']:.8f}")
                    print(f"    direction: {r['direction']}")
        else:
            print("\n" + "=" * 80)
            print("❌ 未检测到信号")
            print("=" * 80)
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

