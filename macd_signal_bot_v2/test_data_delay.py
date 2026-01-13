#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试交易所数据延迟
用于确定最佳缓冲时间
"""
import os
import sys
import time
from datetime import datetime

# 导入主程序
sys.path.insert(0, os.path.dirname(__file__))
from macd_signal_bot_v2 import build_exchange, fetch_ohlcv

def test_data_delay():
    """测试数据延迟"""
    print("=" * 80)
    print("交易所数据延迟测试")
    print("=" * 80)
    print("\n说明：此测试会在K线收盘后立即查询，检查数据是否已更新")
    print("建议：在接近3分钟整点时运行此脚本（如15:17:50）\n")
    
    try:
        exchange = build_exchange()
    except Exception as e:
        print(f"❌ 连接交易所失败: {e}")
        return
    
    symbol = "BTC/USDT"
    timeframe = "3m"
    
    print(f"测试币种: {symbol}")
    print(f"测试周期: {timeframe}")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n等待下一个3分钟整点...")
    
    # 等待到下一个3分钟整点
    while True:
        now = datetime.now()
        if now.second == 0 and now.minute % 3 == 0:
            print(f"\n✅ K线收盘！时间: {now.strftime('%H:%M:%S')}")
            break
        time.sleep(0.1)
    
    # 在不同延迟下测试数据
    delays = [1, 3, 5, 10, 15, 30]
    results = {}
    
    for delay in delays:
        print(f"\n{'='*80}")
        print(f"测试 {delay} 秒延迟")
        print(f"{'='*80}")
        
        time.sleep(delay)
        
        try:
            # 获取最新K线
            df = fetch_ohlcv(exchange, symbol, timeframe, limit=3)
            
            if df is not None and len(df) >= 2:
                # 检查最后一根K线的时间戳
                last_timestamp = df.iloc[-1]["timestamp"]
                last_time = datetime.fromtimestamp(last_timestamp / 1000)
                
                second_last_timestamp = df.iloc[-2]["timestamp"]
                second_last_time = datetime.fromtimestamp(second_last_timestamp / 1000)
                
                print(f"查询时间: {datetime.now().strftime('%H:%M:%S')}")
                print(f"最后一根K线: {last_time.strftime('%H:%M:%S')}")
                print(f"倒数第二根: {second_last_time.strftime('%H:%M:%S')}")
                
                # 检查数据是否已更新
                time_diff = (datetime.now() - last_time).total_seconds()
                
                if time_diff < 180:  # 如果最后一根K线是3分钟内的
                    print(f"✅ 数据已更新（{time_diff:.1f}秒前的K线）")
                    results[delay] = "✅ 已更新"
                else:
                    print(f"❌ 数据未更新（{time_diff:.1f}秒前的K线）")
                    results[delay] = "❌ 未更新"
            else:
                print(f"❌ 获取数据失败")
                results[delay] = "❌ 失败"
                
        except Exception as e:
            print(f"❌ 错误: {e}")
            results[delay] = f"❌ 错误: {str(e)[:30]}"
    
    # 总结
    print(f"\n{'='*80}")
    print("测试总结")
    print(f"{'='*80}\n")
    
    print("| 延迟 | 结果 |")
    print("|------|------|")
    for delay, result in results.items():
        print(f"| {delay:>4}秒 | {result} |")
    
    print("\n建议：")
    for delay, result in results.items():
        if "✅" in result:
            print(f"✅ {delay}秒延迟可用")
            break
    else:
        print("⚠️  建议使用30秒延迟以确保数据完整")

if __name__ == "__main__":
    test_data_delay()

