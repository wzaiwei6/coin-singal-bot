#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 多周期共振监控系统 V2
都是在收盘价进行检测。
-------------------------
监控MACD指标（12, 26, 9），以1h反转为触发点，检查15m/5m/3m共振：

核心逻辑：
1. 只有1h发生反转时才启动检查
2. 检查15m/5m/3m是否与1h方向共振
3. 方向判断：只看Δhist = hist_t - hist_(t-1)
   - Δhist > 0 → 向上
   - Δhist < 0 → 向下
4. 3分钟内不重复发送同方向信号

使用方式：
    # 激活虚拟环境（如果使用）
    source venv/bin/activate
    
    # 运行脚本
    python macd_signal_bot_v2.py

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
from typing import Optional, Dict, Tuple, List

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
    "PIEVERSE/USDT",
    "WLD/USDT",
    "DYM/USDT",
    "ZEC/USDT",
    "BEAT/USDT",
    "PORT3/USDT",
    "TAO/USDT",
    "TRUMP/USDT",
    "HYPE/USDT",
    "AVAX/USDT",
    "GRASS/USDT",
]

# 周期配置：1h为触发器，15m/5m/3m为共振验证
TRIGGER_TIMEFRAME = "1h"
RESONANCE_TIMEFRAMES = ["15m", "5m", "3m"]
ALL_TIMEFRAMES = [TRIGGER_TIMEFRAME] + RESONANCE_TIMEFRAMES

# MACD参数
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# 定时轮询配置
POLL_INTERVAL = 180  # 轮询间隔（秒），默认3分钟

# 调试模式：显示详细的检测日志
DEBUG_MODE = os.getenv("MACD_DEBUG", "false").lower() == "true"

# 状态文件路径
STATE_FILE = os.path.join(os.path.dirname(__file__), ".macd_state_v2.json")

# 企业微信配置
SEND_WECHAT = True
WECHAT_WEBHOOK_URL = os.getenv("MACD_WECHAT_WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=b2715d3d-b8a7-4f07-8938-a9d42b04e9a7")

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
    # return False, None
    # 默认使用代理（本地开发环境）
    return True, "http://127.0.0.1:7890"

USE_PROXY, PROXY_URL = detect_proxy()
EXCHANGE_ID = os.getenv("MACD_EXCHANGE", "binanceusdm")

# ======================= 工具函数 =======================


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
    next_close_time = next_close_time + timedelta(seconds=10)
    
    wait_seconds = (next_close_time - now).total_seconds()
    
    if wait_seconds < 0:
        wait_seconds = 0
    
    return wait_seconds, next_close_time


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


def detect_direction(df: pd.DataFrame, timeframe: str = "", symbol: str = "", debug: bool = False, use_closed_candles: bool = True) -> Optional[str]:
    """
    检测单个周期的柱方向（基于 Δhist）
    
    参数:
        use_closed_candles: 如果为True，使用倒数第2和第3根K线（已收盘），否则使用最后两根
    
    返回:
        "up": 向上（Δhist > 0）
        "down": 向下（Δhist < 0）
        None: 无法判断（数据不足或相等）
    """
    required_len = 3 if use_closed_candles else 2
    if len(df) < required_len:
        return None
    
    # 使用已收盘的K线：倒数第2根和第3根
    if use_closed_candles:
        current_hist = df.iloc[-2]["macd_hist"]
        prev_hist = df.iloc[-3]["macd_hist"]
        current_timestamp = df.iloc[-2]["timestamp"]
        prev_timestamp = df.iloc[-3]["timestamp"]
    else:
        current_hist = df.iloc[-1]["macd_hist"]
        prev_hist = df.iloc[-2]["macd_hist"]
        current_timestamp = df.iloc[-1]["timestamp"]
        prev_timestamp = df.iloc[-2]["timestamp"]
    
    # 检查是否有NaN值
    if pd.isna(current_hist) or pd.isna(prev_hist):
        return None
    
    # 计算Δhist
    delta = current_hist - prev_hist
    
    # 调试日志
    if debug and timeframe and symbol:
        current_time_str = datetime.fromtimestamp(current_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        prev_time_str = datetime.fromtimestamp(prev_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        candle_status = "(已收盘)" if use_closed_candles else "(实时)"
        print(f"  [{timeframe}] 当前K线{candle_status}: {current_time_str}, hist={current_hist:.8f}")
        print(f"  [{timeframe}] 前一K线{candle_status}: {prev_time_str}, hist={prev_hist:.8f}")
        print(f"  [{timeframe}] Δhist={delta:.8f}, 方向={'向上' if delta > 0 else '向下' if delta < 0 else '持平'}")
    
    if delta > 0:
        return "up"
    elif delta < 0:
        return "down"
    else:
        return None  # 完全相等的情况


def detect_1h_reversal(df_1h: pd.DataFrame, symbol: str = "", debug: bool = False) -> Optional[str]:
    """
    检测1h反转（使用已收盘的K线）
    
    向下反转：前一根Δhist >= 0，当前根Δhist < 0
    向上反转：前一根Δhist <= 0，当前根Δhist > 0
    
    返回:
        "down": 向下反转
        "up": 向上反转
        None: 无反转
    """
    if len(df_1h) < 4:  # 需要4根K线：倒数1,2,3,4
        return None
    
    # 获取当前方向（使用已收盘的K线）
    curr_dir = detect_direction(df_1h, "1h", symbol, debug, use_closed_candles=True)
    if curr_dir is None:
        return None
    
    # 计算前一根的Δhist（使用倒数第3和第4根）
    prev_hist = df_1h.iloc[-3]["macd_hist"]
    prev2_hist = df_1h.iloc[-4]["macd_hist"]
    prev2_timestamp = df_1h.iloc[-4]["timestamp"]
    
    if pd.isna(prev_hist) or pd.isna(prev2_hist):
        return None
    
    prev_delta = prev_hist - prev2_hist
    
    # 调试日志
    if debug and symbol:
        prev2_time_str = datetime.fromtimestamp(prev2_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  [1h] 前二K线(已收盘): {prev2_time_str}, hist={prev2_hist:.8f}")
        print(f"  [1h] 前一Δhist={prev_delta:.8f} ({'向上' if prev_delta > 0 else '向下' if prev_delta < 0 else '持平'})")
        print(f"  [1h] 当前方向={curr_dir}, 前一方向={'up' if prev_delta > 0 else 'down' if prev_delta < 0 else 'flat'}")
    
    # 检查反转条件
    if curr_dir == "down" and prev_delta >= 0:
        if debug:
            print(f"  ✅ [1h] 检测到向下反转！")
        return "down"  # 向下反转
    elif curr_dir == "up" and prev_delta <= 0:
        if debug:
            print(f"  ✅ [1h] 检测到向上反转！")
        return "up"  # 向上反转
    
    return None


def check_resonance(exchange: ccxt.binance, symbol: str, reversal_direction: str, debug: bool = False) -> Optional[Dict]:
    """
    检查15m/5m/3m是否与1h方向共振
    
    参数:
        exchange: 交易所对象
        symbol: 交易对
        reversal_direction: 1h反转方向 ("up" 或 "down")
        debug: 是否输出调试信息
    
    返回:
        如果共振成功，返回包含各周期数据的字典
        如果不共振，返回None
    """
    resonance_data = {}
    
    if debug:
        print(f"\n🔍 检查共振周期（期望方向: {reversal_direction}）:")
    
    for timeframe in RESONANCE_TIMEFRAMES:
        try:
            # 获取K线数据
            df = fetch_ohlcv(exchange, symbol, timeframe, limit=50)
            if df is None or len(df) < 37:
                return None
            
            # 计算MACD
            df = calc_macd(df, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
            
            # 检测方向（使用已收盘的K线）
            direction = detect_direction(df, timeframe, symbol, debug, use_closed_candles=True)
            
            # 如果方向不匹配，共振失败
            if direction != reversal_direction:
                if debug:
                    print(f"  ❌ [{timeframe}] 方向不匹配！期望={reversal_direction}, 实际={direction}")
                return None
            
            # 记录该周期的数据（使用已收盘的K线）
            current_hist = df.iloc[-2]["macd_hist"]
            prev_hist = df.iloc[-3]["macd_hist"]
            delta = current_hist - prev_hist
            
            resonance_data[timeframe] = {
                "direction": direction,
                "hist": current_hist,
                "delta": delta,
                "dif": df.iloc[-1]["dif"],
                "dea": df.iloc[-1]["dea"],
                "close": df.iloc[-1]["close"],
            }
            
            if debug:
                print(f"  ✅ [{timeframe}] 共振成功！方向={direction}")
            
        except Exception as e:
            print(f"⚠️  检查 {symbol} {timeframe} 共振时出错：{e}")
            return None
    
    return resonance_data


def check_symbol_signal(exchange: ccxt.binance, symbol: str, debug: bool = False) -> Optional[Dict]:
    """
    检查单个交易对的完整信号（1h反转 + 共振）
    
    返回:
        {
            "direction": "up"/"down",
            "trigger": {...},  # 1h数据
            "resonance": {...}  # 15m/5m/3m数据
        }
        或 None
    """
    try:
        if debug:
            print(f"\n{'='*60}")
            print(f"🔍 开始检查 {symbol} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
        
        # 1. 获取1h数据并检测反转
        df_1h = fetch_ohlcv(exchange, symbol, TRIGGER_TIMEFRAME, limit=50)
        if df_1h is None or len(df_1h) < 37:
            return None
        
        df_1h = calc_macd(df_1h, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        
        if debug:
            print(f"\n📊 检查1h反转:")
        
        reversal_direction = detect_1h_reversal(df_1h, symbol, debug)
        if reversal_direction is None:
            if debug:
                print(f"  ❌ 未检测到1h反转")
            return None
        
        # 2. 检查共振
        resonance_data = check_resonance(exchange, symbol, reversal_direction, debug)
        if resonance_data is None:
            if debug:
                print(f"  ❌ 共振检查失败")
            return None
        
        # 3. 记录1h数据（使用已收盘的K线）
        current_hist = df_1h.iloc[-2]["macd_hist"]
        prev_hist = df_1h.iloc[-3]["macd_hist"]
        delta = current_hist - prev_hist
        
        trigger_data = {
            "direction": reversal_direction,
            "hist": current_hist,
            "delta": delta,
            "dif": df_1h.iloc[-1]["dif"],
            "dea": df_1h.iloc[-1]["dea"],
            "close": df_1h.iloc[-1]["close"],
        }
        
        if debug:
            print(f"\n✅ 信号检测成功！方向: {reversal_direction}")
            print(f"{'='*60}\n")
        
        return {
            "direction": reversal_direction,
            "trigger": trigger_data,
            "resonance": resonance_data
        }
        
    except Exception as e:
        print(f"⚠️  检查 {symbol} 信号时出错：{e}")
        return None


def format_resonance_message(symbol: str, result: Dict) -> str:
    """格式化共振告警消息"""
    direction = result["direction"]
    trigger = result["trigger"]
    resonance = result["resonance"]
    
    # 方向文本和emoji
    if direction == "up":
        direction_emoji = "🔴"
        direction_text = "向上反转"
    else:
        direction_emoji = "🟢"
        direction_text = "向下反转"
    
    # 构建消息
    message = f"[MACD共振] {symbol} {direction_emoji} {direction_text}\n"
    message += f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    message += f"触发：1h ✓ / 15m ✓ / 5m ✓ / 3m ✓\n"
    # message += f"触发：1h 反转{direction_text}\n"
    # message += f"共振：15m ✓ / 5m ✓ / 3m ✓\n\n"
    
    # # 1h数据
    # message += f"1h:  hist={trigger['hist']:>10.6f} (Δ={trigger['delta']:>10.6f})\n"
    
    # # 共振周期数据
    # for tf in RESONANCE_TIMEFRAMES:
    #     if tf in resonance:
    #         r = resonance[tf]
    #         message += f"{tf:>3s}: hist={r['hist']:>10.6f} (Δ={r['delta']:>10.6f})\n"
    
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


def is_already_sent(state: Dict[str, int], symbol: str, direction: str, timestamp: int) -> bool:
    """检查该信号是否已经发送过（3分钟内不重复发送）"""
    key = f"{symbol}_{direction}"
    last_timestamp = state.get(key, 0)
    # 如果3分钟内发送过，不重复发送
    if last_timestamp > 0 and (timestamp - last_timestamp) < 180:
        return True
    return False


def update_state(state: Dict[str, int], symbol: str, direction: str, timestamp: int) -> None:
    """更新状态"""
    key = f"{symbol}_{direction}"
    state[key] = timestamp


def process_symbol(exchange: ccxt.binance, symbol: str, state: Dict[str, int], debug: bool = False) -> bool:
    """处理单个交易对，返回是否检测到信号"""
    try:
        result = check_symbol_signal(exchange, symbol, debug)
        if not result:
            return False
        
        direction = result["direction"]
        current_timestamp = int(time.time())
        
        # 检查是否已经发送过
        if is_already_sent(state, symbol, direction, current_timestamp):
            if debug:
                print(f"⚠️  {symbol} {direction} 信号在3分钟内已发送过，跳过")
            return False
        
        # 更新状态
        update_state(state, symbol, direction, current_timestamp)
        
        # 生成并发送消息
        message = format_resonance_message(symbol, result)
        send_message(message)
        
        return True
    except Exception as e:
        print(f"⚠️  处理 {symbol} 出错：{e}")
        return False


def main():
    """主函数：定时轮询监控MACD共振信号"""
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
    
    print(f"\n🚀 MACD多周期共振监控系统 V2 启动")
    print(f"📊 监控 {len(SYMBOLS)} 个交易对")
    print(f"⏰ 触发周期: {TRIGGER_TIMEFRAME} (反转检测)")
    print(f"🔄 共振周期: {', '.join(RESONANCE_TIMEFRAMES)}")
    print(f"📈 MACD参数: ({MACD_FAST}, {MACD_SLOW}, {MACD_SIGNAL})")
    print(f"⏱️  轮询策略: 在3分钟K线收盘后检测（智能等待）")
    print(f"📌 检测策略: 使用已收盘的K线（倒数第2根）")
    print(f"🚫 去重窗口: 3 分钟")
    print(f"💾 状态文件: {STATE_FILE}")
    print(f"🐛 调试模式: {'启用' if DEBUG_MODE else '禁用'}")
    print(f"\n开始监控... (按 Ctrl+C 停止)\n")
    print(f"⚠️  注意：只有当1h反转且所有共振周期同时满足条件时才会发送告警\n")
    print(f"💡 优势：使用已收盘K线，避免实时数据波动，信号更稳定可靠\n")
    
    if DEBUG_MODE:
        print("=" * 60)
        print("🐛 调试模式已启用 - 将显示详细的检测日志")
        print("=" * 60)
        print()
    
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
                    if process_symbol(exchange, symbol, state, DEBUG_MODE):
                        signal_count += 1
                    success_count += 1
                except Exception as exc:
                    error_count += 1
                    print(f"⚠️  处理 {symbol} 出错：{exc}")
            
            # 保存状态
            save_state(state)
            
            print(f"✅ 完成: 成功={success_count}, 失败={error_count}, 信号={signal_count}")
            
            # 智能等待到下一个3分钟K线收盘后
            wait_seconds, next_check_time = wait_for_next_3min_close()
            
            if wait_seconds > 0:
                print(f"⏳ 等待到下一个3分钟K线收盘: {next_check_time.strftime('%H:%M:%S')} ({wait_seconds:.1f}秒)\n")
                time.sleep(wait_seconds)
            else:
                print(f"⏳ 立即开始下一轮检测\n")
                
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
