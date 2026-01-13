#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试编码修复是否成功
"""

from spike_strategy_backtest import load_symbol_data
from pathlib import Path

print("="*60)
print("           测试CSV文件编码修复")
print("="*60)

# 测试加载BTC数据
data_path = Path('/Users/wang/PythonProjects/xingda/data/coin-binance-swap-candle-csv-1h-2025-11-12/')
btc_file = data_path / 'BTC-USDT.csv'

print(f"\n📂 测试文件: {btc_file}")
print(f"📂 文件存在: {btc_file.exists()}\n")

if btc_file.exists():
    symbol, df = load_symbol_data(btc_file)
    
    if df is not None:
        print(f'✅ 成功加载 {symbol}')
        print(f'📊 数据行数: {len(df):,}')
        print(f'📅 时间范围: {df["candle_begin_time"].min()} ~ {df["candle_begin_time"].max()}')
        print(f'💰 平均成交额: {df["quote_volume"].mean():,.0f} U')
        print(f'\n前5行数据：')
        print(df.head())
        print(f'\n✅ 编码问题已修复！可以正常运行回测了。')
    else:
        print('❌ 加载失败')
else:
    print('❌ 文件不存在，请检查数据路径')

print("\n" + "="*60)


