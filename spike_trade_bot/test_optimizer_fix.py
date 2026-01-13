#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试参数优化器的修复是否有效
"""

import spike_strategy_config as config
from spike_strategy_backtest import SpikeStrategyBacktest, load_symbol_data
from pathlib import Path

print("="*80)
print("           🧪 测试参数优化器修复")
print("="*80)

# 加载一个币种的数据
btc_file = config.data_path / 'BTC-USDT.csv'
print(f"\n📂 加载 BTC-USDT 数据...")

symbol, df = load_symbol_data(btc_file)
if df is None:
    print("❌ 数据加载失败")
    exit(1)

# 过滤到2024年
df = df[(df['candle_begin_time'] >= '2024-01-01') & (df['candle_begin_time'] <= '2024-12-31')]
print(f"✅ 加载成功：{len(df)} 根K线\n")

# 测试1：使用默认参数
print("="*80)
print("测试1：默认参数（盈亏比=2.0）")
print("="*80)

engine1 = SpikeStrategyBacktest()
engine1.run_single_symbol(symbol, df)
engine1.finalize()

print(f"交易次数: {len(engine1.result.trades)}")
print(f"胜率: {engine1.result.win_rate:.2f}%")
print(f"ROI: {engine1.result.roi:.2f}%")

# 保存第一次的交易次数
trade_count_1 = len(engine1.result.trades)

# 测试2：修改参数
print("\n" + "="*80)
print("测试2：修改参数（盈亏比=1.5）")
print("="*80)

# 修改配置
original_rr = config.RISK_REWARD_RATIO
config.RISK_REWARD_RATIO = 1.5

# 重新导入模块
import importlib
import spike_strategy_backtest
importlib.reload(spike_strategy_backtest)
from spike_strategy_backtest import SpikeStrategyBacktest as SpikeStrategyBacktest2

engine2 = SpikeStrategyBacktest2()
engine2.run_single_symbol(symbol, df)
engine2.finalize()

print(f"交易次数: {len(engine2.result.trades)}")
print(f"胜率: {engine2.result.win_rate:.2f}%")
print(f"ROI: {engine2.result.roi:.2f}%")

# 恢复配置
config.RISK_REWARD_RATIO = original_rr

# 检查结果
print("\n" + "="*80)
print("           📊 验证结果")
print("="*80)

trade_count_2 = len(engine2.result.trades)

if abs(engine1.result.roi - engine2.result.roi) > 0.01 or trade_count_1 != trade_count_2:
    print("\n✅ 修复成功！参数修改已生效")
    print(f"   测试1 ROI: {engine1.result.roi:.2f}%")
    print(f"   测试2 ROI: {engine2.result.roi:.2f}%")
    print(f"   差异: {abs(engine1.result.roi - engine2.result.roi):.2f}%")
else:
    print("\n❌ 修复失败！参数修改没有生效")
    print(f"   两次结果完全相同：ROI={engine1.result.roi:.2f}%")
    print("\n💡 需要重新设计参数传递机制")

print("\n" + "="*80)


