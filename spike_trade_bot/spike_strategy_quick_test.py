#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Author: will
@Date: 2025-11-21
@Description: 插针策略快速测试（仅测试少量币种）
----------------------------------------------------------------------------------------------------

用于快速验证策略逻辑是否正确，不需要跑完所有币种

执行方式：
    python spike_strategy_quick_test.py
"""

import sys
import pandas as pd
from pathlib import Path

# 导入主程序模块
from spike_strategy_backtest import (
    SpikeStrategyBacktest, load_symbol_data, enrich_dataframe, detect_spike
)
from spike_strategy_config import *

# 快速测试配置
TEST_SYMBOLS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT', 'BNB-USDT']
# 使用配置文件中的时间范围
TEST_START_DATE = start_date
TEST_END_DATE = end_date


def quick_test():
    """快速测试少量币种"""
    print("="*80)
    print("                  🧪 插针策略快速测试")
    print("="*80)
    print(f"测试币种: {', '.join(TEST_SYMBOLS)}")
    print(f"测试时间: {TEST_START_DATE} ~ {TEST_END_DATE}")
    print("="*80 + "\n")
    
    # 加载数据
    print("📂 正在加载数据...")
    data_dict = {}
    
    for symbol in TEST_SYMBOLS:
        symbol_file = data_path / f"{symbol}.csv"
        if not symbol_file.exists():
            print(f"⚠️  文件不存在: {symbol_file}")
            continue
        
        symbol_name, df = load_symbol_data(symbol_file)
        
        if df is None or df.empty:
            print(f"⚠️  {symbol} 数据加载失败")
            continue
        
        # 过滤测试时间范围
        df = df[(df['candle_begin_time'] >= TEST_START_DATE) & 
                (df['candle_begin_time'] <= TEST_END_DATE)]
        
        if len(df) < 200:
            print(f"⚠️  {symbol} 数据不足")
            continue
        
        data_dict[symbol] = df
        print(f"✅ {symbol:15s} | K线数: {len(df)}")
    
    if not data_dict:
        print("\n❌ 没有可用的数据")
        return
    
    print(f"\n✅ 成功加载 {len(data_dict)} 个币种\n")
    
    # 运行回测
    print("🚀 开始回测...\n")
    engine = SpikeStrategyBacktest()
    
    for symbol, df in data_dict.items():
        print(f"回测 {symbol}...", end=" ")
        try:
            engine.run_single_symbol(symbol, df)
            print("✅")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    engine.finalize()
    
    # 输出结果
    print("\n" + "="*80)
    print("                        📊 测试完成！")
    print("="*80)
    
    print(engine.result.summary())
    
    # 保存回测结果到CSV
    if engine.result.trades:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. 保存回测汇总
        summary_file = output_path / f"quick_test_{timestamp}_summary.csv"
        summary_data = {
            "指标": [
                "初始资金(U)", "最终资金(U)", "总收益(U)", "收益率(%)", 
                "总手续费(U)", "总交易次数", "盈利次数", "亏损次数", 
                "胜率(%)", "平均盈利(U)", "平均亏损(U)", "盈亏比", 
                "最大回撤(%)", "夏普比率", "收益回撤比"
            ],
            "数值": [
                f"{engine.result.initial_capital:,.2f}",
                f"{engine.result.final_capital:,.2f}",
                f"{engine.result.total_pnl:,.2f}",
                f"{engine.result.roi:+.2f}",
                f"{engine.result.total_commission:,.2f}",
                engine.result.total_trades,
                engine.result.win_trades,
                engine.result.loss_trades,
                f"{engine.result.win_rate:.2f}",
                f"{engine.result.avg_win:.2f}",
                f"{engine.result.avg_loss:.2f}",
                f"{engine.result.profit_factor:.2f}",
                f"{engine.result.max_drawdown:.2f}",
                f"{engine.result._sharpe_ratio():.2f}",
                f"{engine.result._calmar_ratio():.2f}"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ 回测汇总已保存: {summary_file}")
        
        # 2. 保存交易明细
        trades_file = output_path / f"quick_test_{timestamp}_trades.csv"
        trades_df = pd.DataFrame([
            {
                "币种": t.symbol,
                "方向": t.direction,
                "入场时间": t.entry_time,
                "出场时间": t.exit_time,
                "入场价": t.entry_price,
                "出场价": t.exit_price,
                "止损价": t.stop_loss,
                "止盈价": t.take_profit,
                "仓位": t.size,
                "盈亏(U)": t.pnl,
                "盈亏(%)": t.pnl_pct,
                "手续费": t.commission,
                "平仓原因": t.exit_reason,
            }
            for t in engine.result.trades
        ])
        
        trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
        print(f"✅ 交易明细已保存: {trades_file}")
    
    # 显示所有交易
    if engine.result.trades:
        print("\n" + "="*80)
        print("                    📋 所有交易明细")
        print("="*80)
        for i, trade in enumerate(engine.result.trades, 1):
            print(f"{i:3d}. {trade}")
    else:
        print("\n⚠️  未产生任何交易信号")
        print("\n可能的原因：")
        print("  1. 插针信号过滤条件太严格")
        print("  2. 测试时间范围内没有符合条件的插针")
        print("  3. 成交量过滤条件太高")
        print("\n建议：")
        print("  1. 在 spike_strategy_config.py 中降低 ATR_MULTIPLIER（如改为 1.5）")
        print("  2. 降低 VOLUME_MULTIPLIER（如改为 1.5）")
        print("  3. 扩大测试时间范围")


def test_spike_detection():
    """测试插针检测功能"""
    print("="*80)
    print("                  🔍 插针检测功能测试")
    print("="*80)
    
    # 加载BTC数据
    btc_file = data_path / "BTC-USDT.csv"
    if not btc_file.exists():
        print(f"❌ 文件不存在: {btc_file}")
        return
    
    print("📂 加载 BTC-USDT 数据...")
    symbol_name, df = load_symbol_data(btc_file)
    
    if df is None or df.empty:
        print("❌ 数据加载失败")
        return
    
    # 只看最近1000根K线
    df = df.tail(1000)
    
    print(f"✅ 成功加载 {len(df)} 根K线\n")
    
    # 计算指标
    print("🔧 计算技术指标...")
    df = enrich_dataframe(df)
    
    # 检测插针
    print("🔍 检测插针信号...\n")
    
    signals = []
    for i in range(len(df)):
        signal = detect_spike(df.iloc[i])
        if signal:
            signals.append((i, df.iloc[i], signal))
    
    print(f"✅ 发现 {len(signals)} 个插针信号\n")
    
    if signals:
        print("="*80)
        print("                    📋 插针信号详情")
        print("="*80)
        
        for idx, (i, row, signal_type) in enumerate(signals[:20], 1):  # 只显示前20个
            direction = "📈 下插针(多头)" if signal_type == "bullish" else "📉 上插针(空头)"
            print(f"\n{idx}. {direction}")
            print(f"   时间: {row['candle_begin_time']}")
            print(f"   价格: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}")
            print(f"   ATR: {row['atr']:.2f} | 振幅/ATR: {row['range']/row['atr']:.2f}x")
            print(f"   成交量Z: {row['volume_z']:.2f} | 成交量倍数: {row['volume']/row['volume_med']:.2f}x")
            
            if signal_type == "bullish":
                print(f"   下影线/实体: {row['lower_shadow']/row['body']:.2f}x")
            else:
                print(f"   上影线/实体: {row['upper_shadow']/row['body']:.2f}x")
        
        if len(signals) > 20:
            print(f"\n... 还有 {len(signals) - 20} 个信号未显示 ...")
    else:
        print("⚠️  未检测到任何插针信号")
        print("\n建议：降低过滤条件（在 spike_strategy_config.py 中）")


def main():
    print("\n请选择测试模式：")
    print("1. 快速回测（测试完整策略）")
    print("2. 插针检测测试（只测试信号检测）")
    print()
    
    choice = input("请输入选项（1 或 2）：").strip()
    
    if choice == "1":
        quick_test()
    elif choice == "2":
        test_spike_detection()
    else:
        print("❌ 无效的选项")


if __name__ == "__main__":
    main()

