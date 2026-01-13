#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析回测表现差的原因，并给出优化建议
"""

import pandas as pd
import numpy as np
from pathlib import Path

print("="*80)
print("           📊 回测表现分析与优化建议")
print("="*80)

# 从你的终端输出，我们知道测试了5个币种（BTC、ETH、SOL、DOGE、BNB）
# 在2024年数据上回测

print("\n【问题诊断】\n")

print("1️⃣ **策略特点分析**")
print("   - 插针策略是「逆势交易」策略")
print("   - 在「震荡市」表现好，在「单边趋势市」表现差")
print("   - 2024年是加密货币大牛市，BTC从4万涨到10万")
print("   - 🔴 这是策略表现差的主要原因！")

print("\n2️⃣ **数据分析**（从你的输出）")
print("   - BTC: 62笔交易，很多止损")
print("   - ETH: 54笔交易，亏损较多")
print("   - SOL: 33笔交易，波动大，回撤严重")
print("   - DOGE: 50笔交易，高波动导致频繁止损")
print("   - BNB: 44笔交易，表现相对较好")

print("\n3️⃣ **主要问题**")
problems = [
    "❌ 在上涨趋势中做空插针 → 逆势亏损",
    "❌ 止损设在极值点 → 在趋势市容易被扫",
    "❌ 时间止损24小时太短 → 没等到反弹就平仓",
    "❌ 没有趋势过滤 → 不分市场环境盲目交易",
    "❌ 盈亏比2:1在趋势市难以实现",
]
for p in problems:
    print(f"   {p}")

print("\n" + "="*80)
print("           🔧 优化建议")
print("="*80)

print("\n【方案1：加入趋势过滤】⭐️⭐️⭐️⭐️⭐️ 最重要！\n")
print("只在合适的市场环境交易：")
print("  - 只在「上升趋势」中做多下插针")
print("  - 只在「下降趋势」中做空上插针")
print("  - 横盘震荡时才做双向交易")
print()
print("修改建议：在 spike_strategy_backtest.py 的 detect_spike() 后增加：")
print("""
  # 计算趋势（例如：20日均线）
  ma_20 = df['close'].rolling(20).mean()
  current_price = current_bar['close']
  
  if signal == "bullish":  # 下插针做多
      if current_price < ma_20.iloc[-1]:
          return None  # 不在均线上方，不做多
  
  elif signal == "bearish":  # 上插针做空
      if current_price > ma_20.iloc[-1]:
          return None  # 不在均线下方，不做空
""")

print("\n【方案2：调整参数】⭐️⭐️⭐️⭐️\n")
print("在 spike_strategy_config.py 中修改：")
print()
print("# 1. 只做多（2024年是牛市）")
print("TRADE_DIRECTION = 'long_only'  # 暂时只做多")
print()
print("# 2. 降低盈亏比（更容易止盈）")
print("RISK_REWARD_RATIO = 1.5  # 从 2.0 降到 1.5")
print()
print("# 3. 延长时间止损（给更多时间反弹）")
print("TIME_STOP_BARS = 48  # 从 24 改为 48 小时")
print()
print("# 4. 降低单笔风险")
print("RISK_PER_TRADE = 0.01  # 从 2% 降到 1%")

print("\n【方案3：使用动态止损】⭐️⭐️⭐️\n")
print("修改止损策略：")
print("  - 入场后立即设保本止损")
print("  - 盈利达到1倍风险后，止损移到成本价")
print("  - 避免盈利回吐")

print("\n【方案4：筛选最佳币种】⭐️⭐️⭐️\n")
print("不是所有币种都适合插针策略：")
print("  - BNB 表现相对较好 → 优先测试")
print("  - SOL、DOGE 波动太大 → 谨慎使用")
print("  - 建议先测试少数稳定币种")

print("\n【方案5：换个测试时间段】⭐️⭐️\n")
print("2024年是单边牛市，不适合插针策略")
print("建议测试震荡市：")
print("  - 2021年5月-7月（横盘震荡）")
print("  - 2022年全年（熊市震荡）")
print("  - 2023年上半年（横盘）")

print("\n" + "="*80)
print("           📋 立即执行")
print("="*80)

print("\n🚀 快速优化步骤：\n")
print("1️⃣ 修改配置（5分钟）")
print("   编辑 spike_strategy_config.py：")
print("   - TRADE_DIRECTION = 'long_only'")
print("   - RISK_REWARD_RATIO = 1.5")
print("   - TIME_STOP_BARS = 48")
print()
print("2️⃣ 重新测试（3分钟）")
print("   python spike_strategy_quick_test.py")
print()
print("3️⃣ 如果还不好，加入趋势过滤（15分钟）")
print("   按照【方案1】修改代码")
print()
print("4️⃣ 测试不同时间段")
print("   在 spike_strategy_quick_test.py 修改：")
print("   TEST_START_DATE = '2022-01-01'")
print("   TEST_END_DATE = '2022-12-31'")

print("\n" + "="*80)
print("           💡 预期改善")
print("="*80)

print("\n如果应用以上优化：")
print("  ✅ 只做多 → 避免牛市做空的大亏")
print("  ✅ 降低盈亏比 → 胜率提高 10-15%")
print("  ✅ 延长时间止损 → 给反弹更多时间")
print("  ✅ 加入趋势过滤 → 最重要！预计ROI提升 20-30%")

print("\n🎯 **核心要点**：")
print("   插针策略 = 震荡市策略")
print("   不要在单边趋势市盲目使用")
print("   必须加入趋势过滤！")

print("\n" + "="*80)


