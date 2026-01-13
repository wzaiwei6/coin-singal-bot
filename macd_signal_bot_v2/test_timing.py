#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试智能轮询时间计算
"""
from datetime import datetime, timedelta

def wait_for_next_3min_close():
    """
    智能等待到下一个3分钟K线收盘后
    
    返回:
        等待的秒数
    """
    now = datetime.now()
    current_minute = now.minute
    current_second = now.second
    
    # 计算当前是第几个3分钟周期（0-19）
    period_in_hour = current_minute // 3
    
    # 计算下一个3分钟整点
    next_period = period_in_hour + 1
    if next_period >= 20:  # 如果超过60分钟，进入下一小时
        next_close_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_minute = next_period * 3
        next_close_time = now.replace(minute=next_minute, second=0, microsecond=0)
    
    # 加30秒缓冲，确保K线已经完全收盘并且数据已更新
    next_close_time = next_close_time + timedelta(seconds=30)
    
    wait_seconds = (next_close_time - now).total_seconds()
    
    if wait_seconds < 0:
        wait_seconds = 0
    
    return wait_seconds, next_close_time


def main():
    """测试时间计算"""
    print("=" * 60)
    print("3分钟K线智能轮询时间测试")
    print("=" * 60)
    
    now = datetime.now()
    print(f"\n当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    wait_seconds, next_check_time = wait_for_next_3min_close()
    
    print(f"下一次检测时间: {next_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"需要等待: {wait_seconds:.1f} 秒 ({wait_seconds/60:.2f} 分钟)")
    
    print("\n" + "=" * 60)
    print("3分钟K线时间点示例：")
    print("=" * 60)
    print("00:00, 00:03, 00:06, 00:09, 00:12, 00:15, 00:18, 00:21, ...")
    print("检测时间会在每个整点后30秒：")
    print("00:00:30, 00:03:30, 00:06:30, 00:09:30, ...")
    
    print("\n" + "=" * 60)
    print("为什么加30秒缓冲？")
    print("=" * 60)
    print("1. K线在整点收盘（如15:18:00）")
    print("2. 交易所需要时间处理和推送数据")
    print("3. 加30秒确保数据已完全更新")
    print("4. 避免获取到不完整的数据")


if __name__ == "__main__":
    main()

