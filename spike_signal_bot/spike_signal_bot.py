#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spike Signal Bot
----------------
在多个交易对 / 多个周期上监控"插针"K线，类似示例中的提示：

1. 通过 ccxt 获取最新 K 线
2. 计算 ATR、range_z、volume_z、主导影线比例
3. 满足条件则格式化输出消息（支持 Telegram 和企业微信）

使用方式：
    # 激活虚拟环境（如果使用）
    source venv/bin/activate
    
    # 运行脚本
    python spike_signal_bot.py

环境变量（可选）：
    SPIKE_BOT_TOKEN          -> Telegram Bot Token
    SPIKE_CHAT_ID            -> Telegram 聊天室 ID
    SPIKE_WECHAT_WEBHOOK_URL -> 企业微信 Webhook URL（默认已配置）
    SPIKE_MESSAGE_FORMAT     -> 消息格式: "format1", "format2", "both" (默认: both)
    SPIKE_USE_PROXY          -> 是否使用代理 (true/false)
    SPIKE_PROXY_URL          -> 代理地址 (默认: http://127.0.0.1:7890)
    SPIKE_EXCHANGE           -> 交易所ID (默认: binanceusdm)
"""
from __future__ import annotations

import os
import sys
import time
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Dict

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
    "BNB/USDT",
    "WLD/USDT",
    "XRP/USDT",
    "ZEC/USDT",
    "LINK/USDT",
    "LTC/USDT",
]
TIMEFRAMES = ["3m", "15m", "1h"]

ATR_PERIOD = 14
SHADOW_RATIO = 2.0             # 主导影线 >= ratio * 实体（可配置为 2.0）
ATR_RATIO = 1.1                # 振幅 >= ATR_RATIO * ATR
ATR_MULTIPLIER = 2.0           # 振幅 >= ATR_MULTIPLIER * ATR（增强过滤）
RANGE_Z_THRESHOLD = 0.0        # 波动量 Z-score
VOLUME_Z_THRESHOLD = 0.5       # 成交量 Z-score
VOLUME_MULTIPLIER = 2.0        # 成交量 >= 平均成交量 × VOLUME_MULTIPLIER
Z_WINDOW = 120                 # 计算 Z-score 的窗口
HISTORY_LIMIT = 400

# 定时轮询配置
POLL_INTERVAL = 300            # 轮询间隔（秒），默认5分钟

# 消息格式配置： "format1", "format2", "both"
MESSAGE_FORMAT = os.getenv("SPIKE_MESSAGE_FORMAT", "both")

# 状态文件路径
STATE_FILE = os.path.join(os.path.dirname(__file__), ".spike_state.json")

# Telegram 配置
SEND_TELEGRAM = True
TELEGRAM_TOKEN = os.getenv("SPIKE_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("SPIKE_CHAT_ID")

# 企业微信配置
SEND_WECHAT = True
WECHAT_WEBHOOK_URL = os.getenv("SPIKE_WECHAT_WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ca74d47c-faa9-4700-bd23-2fbf9dd27bea")

# 本地代理配置：默认禁用代理（服务器部署时不需要代理）
def detect_proxy():
    """自动检测代理设置"""
    # 如果明确设置为 false，则禁用代理
    if os.getenv("SPIKE_USE_PROXY", "").lower() == "false":
        return False, None
    
    # 如果明确设置为 true，则启用代理
    if os.getenv("SPIKE_USE_PROXY", "").lower() == "true":
        proxy_url = os.getenv("SPIKE_PROXY_URL", "http://127.0.0.1:7890")
        return True, proxy_url
    
    # 检测系统代理环境变量（如果设置了系统代理，自动使用）
    for env_var in ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]:
        proxy_url = os.getenv(env_var)
        if proxy_url:
            return True, proxy_url
    
    # 如果设置了 SPIKE_PROXY_URL，使用它
    custom_proxy = os.getenv("SPIKE_PROXY_URL")
    if custom_proxy:
        return True, custom_proxy
    
    # 默认不使用代理（适用于服务器部署）
    return False, None

USE_PROXY, PROXY_URL = detect_proxy()
EXCHANGE_ID = os.getenv("SPIKE_EXCHANGE", "binanceusdm")

# ======================= 工具函数 =======================


def build_exchange():
    """构建交易所对象，支持重试和错误处理"""
    try:
        exchange_class = getattr(ccxt, EXCHANGE_ID)
    except AttributeError:
        raise ValueError(f"不支持的交易所: {EXCHANGE_ID}。请检查环境变量 SPIKE_EXCHANGE")
    
    cfg = {
        "enableRateLimit": True,
        "timeout": 30000,  # 增加超时时间到30秒
        "options": {"defaultType": "future"},
    }
    if USE_PROXY and PROXY_URL:
        cfg["proxies"] = {"http": PROXY_URL, "https": PROXY_URL}
        print(f"✅ 使用代理: {PROXY_URL}")
        print(f"💡 如需更换代理端口，请设置: export SPIKE_PROXY_URL=http://127.0.0.1:你的端口")
    else:
        print("⚠️  代理已禁用")
        print("💡 如需启用代理，请设置: export SPIKE_USE_PROXY=true")
    
    exchange = exchange_class(cfg)
    
    # 重试加载市场数据
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
                    f"   export SPIKE_USE_PROXY=true\n"
                    f"   export SPIKE_PROXY_URL=http://127.0.0.1:7890  # 根据你的代理端口调整\n"
                    f"3. 或者使用其他可用的交易所（如 binance, okx 等）\n"
                )
                raise ConnectionError(error_msg) from e


def fetch_ohlcv(exchange: ccxt.binance, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return df


def calc_atr(df: pd.DataFrame, period: int) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def calc_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window // 2).mean()
    std = series.rolling(window, min_periods=window // 2).std(ddof=0)
    return (series - mean) / std


def tz_beijing(ts: pd.Timestamp | float) -> str:
    if isinstance(ts, pd.Timestamp):
        utc_time = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
    else:
        utc_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    local_time = utc_time + timedelta(hours=8)
    return local_time.strftime("%Y-%m-%d %H:%M:%S")


def tz_beijing_with_tz(ts: pd.Timestamp | float) -> str:
    """转换为北京时间并包含时区信息（UTC+9）"""
    if isinstance(ts, pd.Timestamp):
        utc_time = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
    else:
        utc_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    # 注意：截图显示的是 UTC+9，但通常币安是 UTC+8，这里按截图格式使用 UTC+9
    local_time = utc_time + timedelta(hours=9)
    return local_time.strftime("%Y-%m-%d %H:%M:%S+09:00")


def get_kline_time_range(timestamp: pd.Timestamp | float, timeframe: str) -> tuple[str, str]:
    """计算K线的开始和结束时间（UTC+9时区）"""
    if isinstance(timestamp, pd.Timestamp):
        utc_time = timestamp.tz_convert("UTC") if timestamp.tzinfo else timestamp.tz_localize("UTC")
    else:
        utc_time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    
    # 解析 timeframe
    timeframe_map = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
    }
    
    duration = timeframe_map.get(timeframe, timedelta(hours=1))
    start_time = utc_time
    end_time = utc_time + duration
    
    # 转换为 UTC+9
    start_local = start_time + timedelta(hours=9)
    end_local = end_time + timedelta(hours=9)
    
    return (
        start_local.strftime("%Y-%m-%d %H:%M:%S+09:00"),
        end_local.strftime("%Y-%m-%d %H:%M:%S+09:00")
    )


def load_state() -> Dict[str, int]:
    """加载状态文件，返回已处理的K线时间戳字典"""
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


def is_already_sent(state: Dict[str, int], symbol: str, timeframe: str, timestamp: int) -> bool:
    """检查该K线是否已经发送过"""
    key = f"{symbol}_{timeframe}"
    last_timestamp = state.get(key, 0)
    return timestamp <= last_timestamp


def update_state(state: Dict[str, int], symbol: str, timeframe: str, timestamp: int) -> None:
    """更新状态，记录已处理的K线时间戳"""
    key = f"{symbol}_{timeframe}"
    state[key] = timestamp


def format_message_v1(symbol: str, timeframe: str, row: pd.Series, direction: str, reason: str) -> str:
    """格式1：当前格式 [Spike-T1]"""
    arrow = "多头反转 ↑ (下插针)" if direction == "bullish" else "空头反转 ↓ (上插针)"
    symbol_name = symbol.replace("/", "")
    stamp = tz_beijing(row["timestamp"])
    atr_val = row["atr"]
    body = row["body"]
    shadow = row["lower_shadow"] if direction == "bullish" else row["upper_shadow"]
    range_val = row["range"]
    range_z = row["range_z"]
    vol_z = row["volume_z"]
    vol_ratio = row["volume"] / row.get("volume_med", 1.0)

    message = (
        f"[Spike-T1] {symbol_name} {timeframe} {arrow}\n"
        f"收盘时间（北京时间）：{stamp}\n"
        f"收盘价：{row['close']:.4f}\n"
        f"振幅：{range_val:.2f}  ATR({ATR_PERIOD}): {atr_val:.2f}  range_Z: {range_z:.2f}\n"
        f"主导影线：{shadow:.2f} >= {SHADOW_RATIO:.2f} * {body:.2f}\n"
        f"成交量：Z={vol_z:.2f} xMed={vol_ratio:.2f}\n"
    )

    if reason:
        message += "\n📎 反转确认提醒\n" + reason
    return message


def format_message_v2(symbol: str, timeframe: str, row: pd.Series, direction: str, df: pd.DataFrame) -> str:
    """格式2：插针行情提醒格式（截图2格式）"""
    signal_type = "下插针" if direction == "bullish" else "上插针"
    start_time, end_time = get_kline_time_range(row["timestamp"], timeframe)
    atr_val = row["atr"]
    range_val = row["range"]
    vol_ratio = row["volume"] / row.get("volume_med", 1.0)
    
    # 显示原始成交量（已通过过滤）
    volume_display = int(row["volume"])
    
    message = (
        f"插针行情提醒\n"
        f"标的：{symbol}  周期：{timeframe}\n"
        f"信号：{signal_type}\n"
        f"O/H/L/C：{row['open']:.4f} / {row['high']:.4f} / {row['low']:.4f} / {row['close']:.4f}\n"
        f"成交量：{volume_display} (filtered by average volume × {VOLUME_MULTIPLIER:.1f})\n"
        f"ATR({ATR_PERIOD})：{atr_val:.6f} | 阈值：{ATR_MULTIPLIER:.2f} × ATR\n"
        f"时间：{start_time} ~ {end_time}\n"
        f"解释：影线显著+振幅极端+放量 → 高概率\"插针\""
    )
    return message


def format_message(symbol: str, timeframe: str, row: pd.Series, direction: str, reason: str, df: pd.DataFrame = None) -> str:
    """根据配置选择消息格式"""
    if MESSAGE_FORMAT == "format1":
        return format_message_v1(symbol, timeframe, row, direction, reason)
    elif MESSAGE_FORMAT == "format2":
        if df is None:
            raise ValueError("format2 需要 DataFrame 参数")
        return format_message_v2(symbol, timeframe, row, direction, df)
    elif MESSAGE_FORMAT == "both":
        msg1 = format_message_v1(symbol, timeframe, row, direction, reason)
        if df is not None:
            msg2 = format_message_v2(symbol, timeframe, row, direction, df)
            return msg1 + "\n\n" + msg2
        return msg1
    else:
        # 默认使用 format1
        return format_message_v1(symbol, timeframe, row, direction, reason)


def confirm_reason(symbol: str, timeframe: str, row: pd.Series, prev: pd.Series) -> str:
    body_min = min(prev["open"], prev["close"])
    body_max = max(prev["open"], prev["close"])
    in_prev_body = body_min <= row["close"] <= body_max
    atr_val = row["atr"]
    confirm_parts = [
        f"· 标的：{symbol}  周期：{timeframe}",
        f"· 振幅：{row['range']:.2f} ≈ {row['range']/atr_val:.2f} × ATR",
    ]
    if in_prev_body:
        confirm_parts.append("· 当前收盘已回到上一根实体区间 → 反转概率+")
    confirm_parts.append("· 筛选：主导影线与成交量扩张 + ATR 过滤，排除噪声")
    return "\n".join(confirm_parts)


def send_telegram(text: str) -> None:
    """发送消息到 Telegram"""
    if not (SEND_TELEGRAM and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️  Telegram 发送失败：{resp.text}")
    except Exception as e:
        print(f"⚠️  Telegram 发送异常：{e}")


def send_wechat(text: str) -> None:
    """发送消息到企业微信"""
    if not (SEND_WECHAT and WECHAT_WEBHOOK_URL):
        return
    try:
        # 企业微信webhook支持text和markdown格式
        # 使用text格式更简单可靠
        payload = {
            "msgtype": "text",
            "text": {
                "content": text,
                "mentioned_list": []  # 可以@特定用户，这里为空
            }
        }
        resp = requests.post(WECHAT_WEBHOOK_URL, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") != 0:
            print(f"⚠️  企业微信发送失败：{result.get('errmsg', '未知错误')}")
    except Exception as e:
        print(f"⚠️  企业微信发送异常：{e}")


def send_message(text: str) -> None:
    """统一消息发送接口，同时发送到Telegram和企业微信"""
    # 打印到控制台
    print(text)
    print("-" * 60)
    
    # 发送到Telegram
    send_telegram(text)
    
    # 发送到企业微信
    send_wechat(text)


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["range"] = df["high"] - df["low"]
    df["body"] = (df["close"] - df["open"]).abs().replace(0, 1e-8)
    df["upper_shadow"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_shadow"] = df[["open", "close"]].min(axis=1) - df["low"]
    df["atr"] = calc_atr(df, ATR_PERIOD)
    df["range_z"] = calc_zscore(df["range"], Z_WINDOW)
    df["volume_z"] = calc_zscore(df["volume"], Z_WINDOW)
    df["volume_med"] = df["volume"].rolling(Z_WINDOW, min_periods=Z_WINDOW // 2).median()
    return df


def detect_spike(row: pd.Series) -> Optional[str]:
    """检测插针信号，增强过滤条件"""
    if pd.isna(row["atr"]) or row["atr"] == 0:
        return None
    
    range_ratio = row["range"] / row["atr"]
    direction = None
    
    # 检测主导影线
    if row["lower_shadow"] >= SHADOW_RATIO * row["body"]:
        direction = "bullish"
        shadow = row["lower_shadow"]
    elif row["upper_shadow"] >= SHADOW_RATIO * row["body"]:
        direction = "bearish"
        shadow = row["upper_shadow"]
    else:
        return None

    # 基础过滤：振幅和波动量 Z-score
    if range_ratio < ATR_RATIO or row["range_z"] < RANGE_Z_THRESHOLD:
        return None
    
    # 基础过滤：成交量 Z-score
    if row["volume_z"] < VOLUME_Z_THRESHOLD:
        return None
    
    # 增强过滤1：振幅 >= ATR_MULTIPLIER * ATR
    if range_ratio < ATR_MULTIPLIER:
        return None
    
    # 增强过滤2：成交量 >= 平均成交量 × VOLUME_MULTIPLIER
    volume_med = row.get("volume_med", 0)
    if volume_med > 0 and row["volume"] < volume_med * VOLUME_MULTIPLIER:
        return None

    row["dominant_shadow"] = shadow
    row["range_ratio"] = range_ratio
    return direction


def process_symbol_tf(exchange: ccxt.binance, symbol: str, timeframe: str, state: Dict[str, int]) -> bool:
    """处理单个交易对和周期，返回是否检测到信号"""
    df = fetch_ohlcv(exchange, symbol, timeframe, HISTORY_LIMIT)
    if df is None or len(df) < ATR_PERIOD + 5:
        return False
    
    df = enrich_dataframe(df)
    last = df.iloc[-2]  # 最近一根已收盘
    prev = df.iloc[-3]
    
    # 检查是否已经处理过
    # timestamp 在 enrich_dataframe 中已转换为 pd.Timestamp
    if isinstance(last["timestamp"], pd.Timestamp):
        last_timestamp = int(last["timestamp"].timestamp() * 1000)
    else:
        # 如果是原始毫秒时间戳
        last_timestamp = int(last["timestamp"])
    
    if is_already_sent(state, symbol, timeframe, last_timestamp):
        return False
    
    direction = detect_spike(last)
    if not direction:
        return False
    
    # 更新状态
    update_state(state, symbol, timeframe, last_timestamp)
    
    # 生成消息
    reason = confirm_reason(symbol, timeframe, last, prev)
    message = format_message(symbol, timeframe, last, direction, reason, df)
    send_message(message)
    
    return True


def main():
    """主函数：定时轮询监控插针信号"""
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
    
    print(f"\n🚀 插针信号机器人启动")
    print(f"📊 监控 {len(SYMBOLS)} 个交易对，{len(TIMEFRAMES)} 个周期")
    print(f"⏰ 轮询间隔: {POLL_INTERVAL} 秒 ({POLL_INTERVAL // 60} 分钟)")
    print(f"📝 消息格式: {MESSAGE_FORMAT}")
    print(f"🔍 过滤条件: ATR倍数={ATR_MULTIPLIER}, 成交量倍数={VOLUME_MULTIPLIER}, 影线比例={SHADOW_RATIO}")
    print(f"💾 状态文件: {STATE_FILE}")
    print(f"\n开始监控... (按 Ctrl+C 停止)\n")
    
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
                for timeframe in TIMEFRAMES:
                    try:
                        if process_symbol_tf(exchange, symbol, timeframe, state):
                            signal_count += 1
                        success_count += 1
                    except Exception as exc:
                        error_count += 1
                        print(f"⚠️  处理 {symbol} {timeframe} 出错：{exc}")
            
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
