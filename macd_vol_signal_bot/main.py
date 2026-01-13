#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 波动率信号机器人 - 主程序

监控加密货币市场，基于 MACD + 波动率策略生成交易信号，
并通过企业微信推送通知。

使用方式:
    python main.py

环境变量（可选）:
    MACD_VOL_USE_PROXY       -> 是否使用代理 (true/false)
    MACD_VOL_PROXY_URL       -> 代理地址
    OPENAI_API_KEY           -> OpenAI API密钥
    DEEPSEEK_API_KEY         -> DeepSeek API密钥
"""
import os
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path

# 检查依赖
try:
    import ccxt
    import pandas as pd
    import numpy as np
    import requests
except ImportError as e:
    error_msg = (
        f"\n❌ 缺少必要的依赖包: {e}\n\n"
        f"💡 解决方案：\n"
        f"1. 激活虚拟环境：\n"
        f"   source venv/bin/activate\n"
        f"2. 安装依赖：\n"
        f"   pip install -r requirements.txt\n"
        f"3. 然后重新运行脚本\n"
    )
    print(error_msg)
    sys.exit(1)

# 导入模块
from market.binance import build_exchange, fetch_klines
from strategy.macd_vol import generate_signal
from dedup.dedup import DedupManager
from notifier.wecom import send_signal, send_startup_notification
from llm.analyzer import analyze_signal


def load_config(config_path: str = "config.yaml") -> dict:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        dict: 配置字典
    """
    script_dir = Path(__file__).parent
    config_file = script_dir / config_path
    
    if not config_file.exists():
        print(f"❌ 配置文件不存在: {config_file}")
        sys.exit(1)
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"✅ 配置文件加载成功: {config_file}")
        return config
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        sys.exit(1)


def process_symbol_timeframe(exchange: ccxt.Exchange, symbol: str, timeframe: str, 
                             config: dict, dedup_mgr: DedupManager) -> None:
    """
    处理单个交易对和时间周期
    
    Args:
        exchange: 交易所对象
        symbol: 交易对
        timeframe: 时间周期
        config: 配置
        dedup_mgr: 去重管理器
    """
    try:
        # 获取K线数量
        history_limit = config.get("strategy", {}).get("history_limit", 200)
        
        # 拉取行情数据
        df = fetch_klines(exchange, symbol, timeframe, limit=history_limit)
        
        if df is None or len(df) < 50:
            print(f"⚠️  {symbol} {timeframe} 数据不足，跳过")
            return
        
        # 获取当前 K 线时间戳
        current_bar_time = int(df.iloc[-1]["timestamp"])
        current_price = float(df.iloc[-1]["close"])
        
        # 执行策略，生成信号
        signal = generate_signal(df, symbol, timeframe, config)
        
        if signal is None:
            # 无信号，但检查是否有关键位事件（针对已存在的信号）
            # 这里可以扩展，暂时跳过
            return
        
        print(f"\n{'='*60}")
        print(f"🎯 检测到信号: {signal.symbol} {signal.timeframe} {signal.direction}")
        print(f"   价格: {signal.price} | 置信度: {signal.confidence*100:.0f}% | 风险: {signal.risk_level}")
        
        # === 核心冷却逻辑 ===
        
        # 1. 检查是否在冷却期
        in_cooldown, bars_passed = dedup_mgr.is_in_cooldown(
            signal.symbol, signal.timeframe, signal.direction, current_bar_time
        )
        
        if in_cooldown:
            # 2. 在冷却期内，检查是否触发关键位事件
            key_level_event = dedup_mgr.check_key_level_trigger(
                signal.symbol,
                signal.timeframe,
                signal.direction,
                current_price,
                signal.key_levels
            )
            
            if key_level_event:
                # 3. 触发关键位，发送确认消息（打破冷却）
                print(f"🚨 关键位事件: {key_level_event['message']}")
                
                wecom_config = config.get("wecom", {})
                if wecom_config.get("enabled", True):
                    webhook_url = wecom_config.get("webhook_url")
                    if webhook_url:
                        # 使用关键位消息格式
                        from notifier.wecom import format_key_level_message, send_text_message
                        message = format_key_level_message(signal, key_level_event)
                        
                        try:
                            payload = {
                                "msgtype": "markdown",
                                "markdown": {"content": message}
                            }
                            response = requests.post(webhook_url, json=payload, timeout=10)
                            result = response.json()
                            
                            if result.get("errcode") == 0:
                                print(f"✅ 关键位确认消息发送成功")
                            else:
                                print(f"⚠️  消息发送失败: {result.get('errmsg')}")
                        except Exception as e:
                            print(f"⚠️  发送关键位消息失败: {e}")
            else:
                # 4. 在冷却期且无关键位事件，跳过
                print(f"⏸️  在冷却期内，跳过发送")
            
            print(f"{'='*60}\n")
            return
        
        # 5. 不在冷却期，正常发送信号
        
        # 调用LLM分析（可能失败，不影响主流程）
        llm_analysis = None
        if config.get("llm", {}).get("enabled", False):
            print("🤖 调用AI分析...")
            llm_analysis = analyze_signal(signal, config)
        
        # 发送企业微信通知
        wecom_config = config.get("wecom", {})
        if wecom_config.get("enabled", True):
            webhook_url = wecom_config.get("webhook_url")
            if webhook_url:
                success = send_signal(signal, webhook_url, llm_analysis)
                
                if success:
                    # 记录已发送的信号（使用当前 K 线时间）
                    dedup_mgr.record_signal(
                        signal.symbol, 
                        signal.timeframe, 
                        signal.direction, 
                        signal.price,
                        current_bar_time  # 记录 K 线时间戳
                    )
                else:
                    print("⚠️  消息发送失败，不记录信号状态")
            else:
                print("⚠️  未配置企业微信 Webhook URL")
        
        print(f"{'='*60}\n")
    
    except Exception as e:
        print(f"❌ 处理 {symbol} {timeframe} 时出错: {e}")
        import traceback
        traceback.print_exc()


def main_loop(config: dict, exchange: ccxt.Exchange, dedup_mgr: DedupManager) -> None:
    """
    主循环 - 遍历所有交易对和时间周期
    
    Args:
        config: 配置
        exchange: 交易所对象
        dedup_mgr: 去重管理器
    """
    symbols = config.get("symbols", [])
    timeframes = config.get("timeframes", [])
    
    print(f"\n{'='*60}")
    print(f"⏰ 开始新一轮扫描 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    for symbol in symbols:
        for timeframe in timeframes:
            print(f"\n🔍 检查 {symbol} {timeframe}...")
            process_symbol_timeframe(exchange, symbol, timeframe, config, dedup_mgr)
            
            # 避免请求过快
            time.sleep(0.5)
    
    print(f"\n{'='*60}")
    print(f"✅ 本轮扫描完成")
    print(f"{'='*60}\n")
    
    # 定期清理过期记录
    dedup_mgr.cleanup_expired(max_age_hours=24)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("🚀 MACD 波动率信号机器人启动")
    print("="*60 + "\n")
    
    # 加载配置
    config = load_config()
    
    # 显示配置信息
    symbols = config.get("symbols", [])
    timeframes = config.get("timeframes", [])
    poll_interval = config.get("runtime", {}).get("poll_interval", 300)
    cooldown_bars = config.get("signal", {}).get("cooldown_bars", 2)
    
    print(f"📊 监控配置:")
    print(f"   币种: {', '.join(symbols)}")
    print(f"   周期: {', '.join(timeframes)}")
    print(f"   轮询间隔: {poll_interval}秒")
    print(f"   冷却机制: {cooldown_bars} 根 K 线")
    print()
    
    # 初始化交易所
    try:
        exchange = build_exchange(config)
    except Exception as e:
        print(f"\n❌ 初始化交易所失败: {e}")
        sys.exit(1)
    
    # 初始化去重管理器
    state_file = config.get("runtime", {}).get("state_file", ".macd_vol_state.json")
    cooldown_bars = config.get("signal", {}).get("cooldown_bars", 2)
    break_on_key_level = config.get("signal", {}).get("break_cooldown_on_key_level", True)
    
    script_dir = Path(__file__).parent
    state_file_path = script_dir / state_file
    
    dedup_mgr = DedupManager(str(state_file_path), cooldown_bars, break_on_key_level)
    
    # 发送启动通知
    wecom_config = config.get("wecom", {})
    if wecom_config.get("enabled", True):
        webhook_url = wecom_config.get("webhook_url")
        if webhook_url:
            send_startup_notification(webhook_url, config)
    
    print(f"\n✅ 初始化完成，开始监控...\n")
    
    # 主循环
    loop_count = 0
    try:
        while True:
            loop_count += 1
            print(f"\n{'#'*60}")
            print(f"# 第 {loop_count} 轮扫描")
            print(f"{'#'*60}")
            
            try:
                main_loop(config, exchange, dedup_mgr)
            except Exception as e:
                print(f"❌ 主循环出错: {e}")
                print("⚠️  5秒后继续...")
                time.sleep(5)
                continue
            
            # 休眠到下一轮
            print(f"\n💤 休眠 {poll_interval} 秒...")
            time.sleep(poll_interval)
    
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("👋 收到中断信号，程序退出")
        print("="*60 + "\n")
        
        # 显示统计信息
        stats = dedup_mgr.get_statistics()
        print(f"📊 运行统计:")
        print(f"   总信号数: {stats['total_signals']}")
        print(f"   信号种类: {stats['total_keys']}")
        print(f"   运行轮数: {loop_count}")
        print()
        
        sys.exit(0)


if __name__ == "__main__":
    main()
