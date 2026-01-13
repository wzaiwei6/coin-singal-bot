#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD Signal Bot
---------------
监控MACD指标（12, 26, 9），当周期满足反转条件时发送告警：

1. 通过 ccxt 获取最新 K 线
2. 计算 MACD 指标（DIF、DEA、MACD柱）
3. 检测反转信号：实柱到虚柱（红变绿）或虚柱到实柱（绿变红）
4. 同方向不告警（继续同方向变化时不发送告警）

使用方式：
    # 激活虚拟环境（如果使用）
    source venv/bin/activate
    
    # 运行脚本
    python macd_signal_bot.py

环境变量（可选）：
    MACD_WECHAT_WEBHOOK_URL -> 企业微信 Webhook URL（默认已配置）
    MACD_USE_PROXY          -> 是否使用代理 (true/false)
    MACD_PROXY_URL          -> 代理地址 (默认: http://127.0.0.1:7890)
    MACD_EXCHANGE           -> 交易所ID (默认: binanceusdm)
"""
from __future__ import annotations

import os
import sys
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple

# 检查并导入依赖
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

# ======================= 配置区 =======================
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "DOGE/USDT",
    "FIL/USDT",
    "WLD/USDT",
    "ZEC/USDT",
    "TRUMP/USDT",
]

TIMEFRAMES = ["5m"]  # 15min trade singal bot

# MACD参数
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# 定时轮询配置
POLL_INTERVAL = 30  # 轮询间隔（秒），30秒轮询一次，确保能及时检测到新完成的K线

# 状态文件路径
STATE_FILE = os.path.join(os.path.dirname(__file__), ".macd_state_5-3.json")

# 企业微信配置
SEND_WECHAT = True
WECHAT_WEBHOOK_URL = os.getenv("MACD_WECHAT_WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=606ded4c-12fa-4e3c-90a1-972d8d71b9b4")

# 本地代理配置：默认禁用代理（服务器部署时不需要代理）
def detect_proxy():
    """自动检测代理设置"""
    # 如果明确设置为 false，则禁用代理
    if os.getenv("MACD_USE_PROXY", "").lower() == "false":
        return False, None
    
    # 如果明确设置为 true，则启用代理
    if os.getenv("MACD_USE_PROXY", "").lower() == "true":
        proxy_url = os.getenv("MACD_PROXY_URL", "http://127.0.0.1:7890")
        return True, proxy_url
    
    # 检测系统代理环境变量（如果设置了系统代理，自动使用）
    for env_var in ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]:
        proxy_url = os.getenv(env_var)
        if proxy_url:
            return True, proxy_url
    
    # 如果设置了 MACD_PROXY_URL，使用它
    custom_proxy = os.getenv("MACD_PROXY_URL")
    if custom_proxy:
        return True, custom_proxy
    
    # 默认不使用代理（适用于服务器部署）
    return False, None

USE_PROXY, PROXY_URL = detect_proxy()
EXCHANGE_ID = os.getenv("MACD_EXCHANGE", "binanceusdm")

# ======================= 工具函数 =======================


def build_exchange():
    """构建交易所对象，支持重试和错误处理"""
    try:
        exchange_class = getattr(ccxt, EXCHANGE_ID)
    except AttributeError:
        raise ValueError(f"不支持的交易所: {EXCHANGE_ID}。请检查环境变量 MACD_EXCHANGE")
    
    cfg = {
        "enableRateLimit": True,
        "timeout": 30000,
        "options": {"defaultType": "future"},
    }
    if USE_PROXY and PROXY_URL:
        cfg["proxies"] = {"http": PROXY_URL, "https": PROXY_URL}
        print(f"✅ 使用代理: {PROXY_URL}")
    else:
        print("⚠️  代理已禁用")
    
    exchange = exchange_class(cfg)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"正在连接交易所 {EXCHANGE_ID}... (尝试 {attempt + 1}/{max_retries})")
            exchange.load_markets()
            print(f"成功连接到 {EXCHANGE_ID}")
            return exchange
        except (ccxt.NetworkError, ccxt.ExchangeError, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"连接失败，{wait_time}秒后重试... 错误: {str(e)[:100]}")
                time.sleep(wait_time)
            else:
                error_msg = (
                    f"\n❌ 无法连接到交易所 {EXCHANGE_ID}\n"
                    f"错误详情: {str(e)}\n\n"
                    f"💡 解决方案：\n"
                    f"1. 检查网络连接\n"
                    f"2. 如果在中国大陆，请设置代理：\n"
                    f"   export MACD_USE_PROXY=true\n"
                    f"   export MACD_PROXY_URL=http://127.0.0.1:7890\n"
                    f"3. 或者使用其他可用的交易所（如 binance, okx 等）\n"
                )
                raise ConnectionError(error_msg) from e


def fetch_ohlcv(exchange: ccxt.binance, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """获取K线数据"""
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return df


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算MACD指标"""
    df = df.copy()
    close = df["close"]
    
    # 计算EMA
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    # 计算DIF（快线-慢线）
    df["dif"] = ema_fast - ema_slow
    
    # 计算DEA（DIF的信号线）
    df["dea"] = df["dif"].ewm(span=signal, adjust=False).mean()
    
    # 计算MACD柱（DIF - DEA）
    df["macd_hist"] = df["dif"] - df["dea"]
    
    return df


def detect_macd_signal(df: pd.DataFrame) -> Optional[str]:
    """
    检测MACD反转信号（使用已完成的K线）
    
    注意：使用倒数第二根和倒数第三根K线（已完成的K线），而不是最后一根（可能未完成）
    
    返回:
        "bullish": 多头反转信号（绿变红，虚柱变实柱）
        "bearish": 空头反转信号（红变绿，实柱变虚柱）
        None: 无信号（同方向不告警）
    """
    if len(df) < 3:
        return None
    
    # 使用已完成的K线：倒数第二根（最新完成的）和倒数第三根（前一根完成的）
    # df.iloc[-1] 可能是正在形成的K线，df.iloc[-2] 是已完成的K线
    current_completed = df.iloc[-2]  # 最新完成的K线
    prev_completed = df.iloc[-3]    # 前一根完成的K线
    
    # 检查是否有NaN值
    if pd.isna(current_completed["macd_hist"]) or pd.isna(prev_completed["macd_hist"]):
        return None
    
    # 检测MACD柱的反转信号
    # 实柱（正数，红色）-> 虚柱（负数，绿色）：空头反转信号
    # 虚柱（负数，绿色）-> 实柱（正数，红色）：多头反转信号
    
    prev_hist = prev_completed["macd_hist"]
    current_hist = current_completed["macd_hist"]
    
    # 空头反转：从实柱（正）变虚柱（负），红变绿
    if prev_hist > 0 and current_hist <= 0:
        return "bearish"
    
    # 多头反转：从虚柱（负）变实柱（正），绿变红
    if prev_hist < 0 and current_hist >= 0:
        return "bullish"
    
    # 同方向不告警（都是正数或都是负数）
    return None


def check_all_timeframes(exchange: ccxt.binance, symbol: str) -> Optional[Dict]:
    """
    检查所有周期是否同时满足条件，并返回统计信息
    
    返回:
        {
            "direction": "bullish"/"bearish", 
            "signals": {...},
            "stats": {...},  # 新增统计信息
            "kline_timestamp": int  # 新增：K线时间戳（用于防重复）
        } 或 None
    """
    signals = {}
    directions = []
    stats = {
        "total": len(TIMEFRAMES),
        "matched": 0,
        "bullish": 0,
        "bearish": 0,
        "no_signal": 0
    }
    kline_timestamp = None  # 记录K线时间戳
    
    for timeframe in TIMEFRAMES:
        try:
            # 获取足够的历史数据（至少需要37根K线用于MACD计算，还需要额外的K线用于检测已完成的K线）
            df = fetch_ohlcv(exchange, symbol, timeframe, limit=50)
            if df is None or len(df) < 37:
                stats["no_signal"] += 1
                return None
            
            # 计算MACD
            df = calc_macd(df, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
            
            # 检测信号
            signal = detect_macd_signal(df)
            
            if signal:
                # 使用已完成的K线数据（倒数第二根）
                completed_kline = df.iloc[-2]
                # 记录K线时间戳（用于防重复，确保同一根K线只发送一次）
                if kline_timestamp is None:
                    kline_timestamp = int(completed_kline["timestamp"] / 1000)  # 转换为秒级时间戳
                signals[timeframe] = {
                    "direction": signal,
                    "dif": completed_kline["dif"],
                    "dea": completed_kline["dea"],
                    "macd_hist": completed_kline["macd_hist"],
                    "close": completed_kline["close"],
                }
                directions.append(signal)
                stats["matched"] += 1
                if signal == "bullish":
                    stats["bullish"] += 1
                else:
                    stats["bearish"] += 1
            else:
                # 如果任何一个周期不满足，返回None
                stats["no_signal"] += 1
                return None
        except Exception as e:
            print(f"⚠️  检查 {symbol} {timeframe} 出错：{e}")
            stats["no_signal"] += 1
            return None
    
    # 检查所有周期是否都是同一方向
    if len(directions) == len(TIMEFRAMES):
        # 检查是否全部是同一方向
        if all(d == directions[0] for d in directions):
            return {
                "direction": directions[0],
                "signals": signals,
                "stats": stats,
                "kline_timestamp": kline_timestamp  # 返回K线时间戳
            }
    
    return None


def format_macd_message(symbol: str, result: Dict) -> str:
    """格式化MACD告警消息"""
    direction = result["direction"]
    signals = result["signals"]
    stats = result.get("stats", {})
    
    if direction == "bullish":
        direction_text = "🔴 多头向上信号"
    else:
        direction_text = "🟢 空头向下信号"
    
    message = f"{symbol} {direction_text}\n"
    message += f"⏰ 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # message += f"\n✅ {len(TIMEFRAMES)}个周期同时满足反转条件！"
    
    return message

def send_wechat(text: str) -> None:
    """发送消息到企业微信"""
    if not (SEND_WECHAT and WECHAT_WEBHOOK_URL):
        return
    try:
        payload = {
            "msgtype": "text",
            "text": {
                "content": text,
                "mentioned_list": []
            }
        }
        resp = requests.post(WECHAT_WEBHOOK_URL, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") != 0:
            print(f"⚠️  企业微信发送失败：{result.get('errmsg', '未知错误')}")
    except Exception as e:
        print(f"⚠️  企业微信发送异常：{e}")


def send_message(text: str) -> None:
    """统一消息发送接口"""
    print(text)
    print("-" * 60)
    send_wechat(text)


def load_state() -> Dict[str, int]:
    """加载状态文件"""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  加载状态文件失败: {e}")
        return {}


def save_state(state: Dict[str, int]) -> None:
    """保存状态文件"""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️  保存状态文件失败: {e}")


def is_already_sent(state: Dict[str, int], symbol: str, direction: str, kline_timestamp: int) -> bool:
    """
    检查该信号是否已经发送过（基于K线时间戳，确保同一根K线只发送一次）
    
    参数:
        kline_timestamp: K线的时间戳（秒级），不是当前时间戳
    """
    key = f"{symbol}_{direction}"
    last_kline_timestamp = state.get(key, 0)
    # 如果K线时间戳相同，说明是同一根K线，不重复发送
    if last_kline_timestamp > 0 and kline_timestamp == last_kline_timestamp:
        return True
    return False


def update_state(state: Dict[str, int], symbol: str, direction: str, kline_timestamp: int) -> None:
    """更新状态（记录K线时间戳）"""
    key = f"{symbol}_{direction}"
    state[key] = kline_timestamp

def process_symbol(exchange: ccxt.binance, symbol: str, state: Dict[str, int]) -> bool:
    """处理单个交易对，返回是否检测到信号"""
    try:
        result = check_all_timeframes(exchange, symbol)
        if not result:
            return False
        
        direction = result["direction"]
        kline_timestamp = result.get("kline_timestamp")
        
        if kline_timestamp is None:
            print(f"⚠️  {symbol} 缺少K线时间戳，跳过")
            return False
        
        # 检查是否已经发送过（基于K线时间戳）
        if is_already_sent(state, symbol, direction, kline_timestamp):
            return False
        
        # 更新状态（记录K线时间戳）
        update_state(state, symbol, direction, kline_timestamp)
        
        # 生成并发送消息
        message = format_macd_message(symbol, result)
        send_message(message)
        
        return True
    except Exception as e:
        print(f"⚠️  处理 {symbol} 出错：{e}")
        return False


def main():
    """主函数：定时轮询监控MACD信号"""
    try:
        exchange = build_exchange()
    except (ConnectionError, ValueError) as e:
        print(e)
        return
    except Exception as e:
        print(f"❌ 初始化交易所失败: {e}")
        return
    
    # 加载状态
    state = load_state()
    
    print(f"\n🚀 MACD反转信号机器人启动")
    print(f"📊 监控 {len(SYMBOLS)} 个交易对")
    print(f"⏰ 监控周期: {', '.join(TIMEFRAMES)} (共{len(TIMEFRAMES)}个)")
    print(f"📈 MACD参数: ({MACD_FAST}, {MACD_SLOW}, {MACD_SIGNAL})")
    print(f"⏱️  轮询间隔: {POLL_INTERVAL} 秒 (每 {POLL_INTERVAL // 60} 分钟)")
    print(f"💾 状态文件: {STATE_FILE}")
    print(f"\n开始监控... (按 Ctrl+C 停止)\n")
    print(f"⚠️  注意：只检测反转信号（实柱↔虚柱，红↔绿），同方向不告警\n")
    
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            cycle_start = time.time()
            
            print(f"[轮询 #{cycle_count}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            success_count = 0
            error_count = 0
            signal_count = 0
            
            for symbol in SYMBOLS:
                try:
                    if process_symbol(exchange, symbol, state):
                        signal_count += 1
                    success_count += 1
                except Exception as exc:
                    error_count += 1
                    print(f"⚠️  处理 {symbol} 出错：{exc}")
            
            # 保存状态
            save_state(state)
            
            print(f"✅ 完成: 成功={success_count}, 失败={error_count}, 信号={signal_count}")
            
            # 计算剩余等待时间
            elapsed = time.time() - cycle_start
            wait_time = max(0, POLL_INTERVAL - elapsed)
            
            if wait_time > 0:
                print(f"⏳ 等待 {wait_time:.1f} 秒后继续...\n")
                time.sleep(wait_time)
            else:
                print(f"⚠️  处理时间过长 ({elapsed:.1f}秒)，立即开始下一轮\n")
                
    except KeyboardInterrupt:
        print(f"\n\n🛑 收到停止信号，正在保存状态...")
        save_state(state)
        print(f"✅ 状态已保存，程序退出")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        save_state(state)
        raise


if __name__ == "__main__":
    main()

