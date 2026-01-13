#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spike Strategy Backtest
-----------------------
回测插针反弹策略，支持本地 CSV 数据和 CCXT 在线下载。

数据源优先级：
1. 本地 CSV (../../data/coin-binance-swap-candle-csv-1h-2025-11-12/)
   - 仅限 1h 周期
   - 自动跳过第一行（广告）
2. CCXT 在线下载
   - 其他周期或本地缺失的币种
"""

import os
import sys
import time
import glob
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ======================= 配置区 =======================
# 本地数据路径
LOCAL_DATA_PATH = "../../data/coin-binance-swap-candle-csv-1h-2025-11-12/"

# 策略参数 (与 spike_signal_bot.py 保持一致)
ATR_PERIOD = 14
SHADOW_RATIO = 2.0
ATR_RATIO = 1.1
ATR_MULTIPLIER = 2.0
RANGE_Z_THRESHOLD = 0.0
VOLUME_Z_THRESHOLD = 0.5
VOLUME_MULTIPLIER = 2.0
Z_WINDOW = 120

# 资金管理
INITIAL_CAPITAL = 10000.0  # 初始资金
RISK_PER_TRADE = 0.02      # 单笔风险 2%
COMMISSION_RATE = 0.0005   # 手续费万五

# 回测标的
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", 
    "BNB/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT"
]
TIMEFRAMES = ["1h", "15m", "4h"]  # 优先回测 1h

# ======================= 指标计算 =======================

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

def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # 确保 timestamp 是 datetime 类型
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
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
    """检测信号 (完全复用 spike_signal_bot 逻辑)"""
    if pd.isna(row["atr"]) or row["atr"] == 0:
        return None
    
    range_ratio = row["range"] / row["atr"]
    direction = None
    shadow = 0.0
    
    # 检测主导影线
    if row["lower_shadow"] >= SHADOW_RATIO * row["body"]:
        direction = "bullish"
        shadow = row["lower_shadow"]
    elif row["upper_shadow"] >= SHADOW_RATIO * row["body"]:
        direction = "bearish"
        shadow = row["upper_shadow"]
    else:
        return None

    # 基础过滤
    if range_ratio < ATR_RATIO or row["range_z"] < RANGE_Z_THRESHOLD:
        return None
    if row["volume_z"] < VOLUME_Z_THRESHOLD:
        return None
    
    # 增强过滤
    if range_ratio < ATR_MULTIPLIER:
        return None
    
    volume_med = row.get("volume_med", 0)
    if volume_med > 0 and row["volume"] < volume_med * VOLUME_MULTIPLIER:
        return None

    return direction

# ======================= 数据提供者 =======================

class DataProvider:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.cache_dir = "backtest_data"
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def load_data(self, symbol: str, timeframe: str, limit: int = 5000) -> pd.DataFrame:
        """智能加载数据：优先本地 CSV (1h)，否则 CCXT 下载"""
        
        # 1. 尝试读取本地 CSV (仅限 1h)
        if timeframe == "1h":
            df = self._load_from_local_csv(symbol)
            if df is not None:
                print(f"✅ [Local] 加载 {symbol} {timeframe} 成功: {len(df)} 条")
                return df

        # 2. 尝试读取缓存
        cache_file = os.path.join(self.cache_dir, f"{symbol.replace('/', '')}_{timeframe}.csv")
        if os.path.exists(cache_file):
            print(f"📦 [Cache] 加载 {symbol} {timeframe}")
            df = pd.read_csv(cache_file)
            df["timestamp"] = pd.to_datetime(df["timestamp"]) # 缓存通常保存为标准时间字符串
            return df

        # 3. CCXT 下载
        print(f"⬇️  [CCXT] 下载 {symbol} {timeframe} ...")
        try:
            since = self.exchange.milliseconds() - (limit * self._tf_to_ms(timeframe))
            all_ohlcv = []
            while len(all_ohlcv) < limit:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                if not ohlcv:
                    break
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 1
                if len(ohlcv) < 1000:
                    break
                time.sleep(0.1)
            
            df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            # 保存缓存
            df.to_csv(cache_file, index=False)
            return df
        except Exception as e:
            print(f"❌ 下载失败 {symbol}: {e}")
            return pd.DataFrame()

    def _load_from_local_csv(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        从指定目录读取 CSV。
        文件名格式假设：包含 symbol (如 BTCUSDT)
        """
        if not os.path.exists(LOCAL_DATA_PATH):
            return None
            
        clean_symbol = symbol.replace("/", "").upper()
        # 简单的文件名匹配
        # 假设文件名为 "BTCUSDT-1h-2025-11-12.csv" 或类似
        pattern = os.path.join(LOCAL_DATA_PATH, f"*{clean_symbol}*.csv")
        files = glob.glob(pattern)
        
        if not files:
            return None
        
        # 取第一个匹配的文件
        target_file = files[0]
        try:
            # skiprows=1 跳过第一行广告
            df = pd.read_csv(target_file, skiprows=1)
            
            # 标准化列名 (假设常见的 binance 导出格式)
            # 常见格式: Open Time, Open, High, Low, Close, Volume, ...
            # 需转换为: timestamp, open, high, low, close, volume
            
            # 移除列名空格并转小写
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            
            # 映射关键列
            col_map = {
                "open_time": "timestamp",
                "open": "open",
                "high": "high", 
                "low": "low",
                "close": "close",
                "volume": "volume"
            }
            
            # 检查是否存在这就几个关键列
            if not all(k in df.columns for k in col_map.keys()):
                # 尝试另一种常见的简单格式 (timestamp, open, high, low, close, volume)
                if "timestamp" in df.columns: 
                    return df[["timestamp", "open", "high", "low", "close", "volume"]]
                print(f"⚠️  [Local] 列名无法识别: {df.columns.tolist()}")
                return None

            df = df.rename(columns=col_map)
            
            # 确保 timestamp 解析正确
            # 币安导出通常是 "2025-01-01 08:00:00" 字符串
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
            
        except Exception as e:
            print(f"⚠️  [Local] 读取失败 {target_file}: {e}")
            return None

    def _tf_to_ms(self, timeframe):
        return self.exchange.parse_timeframe(timeframe) * 1000

# ======================= 回测引擎 =======================

class BacktestEngine:
    def __init__(self, capital=INITIAL_CAPITAL):
        self.initial_capital = capital
        self.balance = capital
        self.trades = []
        self.equity_curve = []
        
    def run(self, df: pd.DataFrame):
        if df.empty:
            return
            
        # 预计算指标
        df = enrich_dataframe(df)
        
        position = None # None, 'long', 'short'
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        size = 0.0
        entry_time = None
        
        for i in range(1, len(df)):
            # 模拟逐根K线推进
            # current_row 是刚刚收盘的 K 线 (index=i)
            # 在实盘中，我们在 i 收盘时决策，在 i+1 开盘时成交（或 i 收盘价成交）
            # 这里假设以 K线 i 的收盘价成交
            
            curr = df.iloc[i]
            prev = df.iloc[i-1] # 前一根
            
            # 1. 检查持仓退出
            if position:
                exit_price = None
                exit_reason = ""
                pnl = 0.0
                
                # 检查当前K线(i)是否触及止损止盈
                # 注意：我们假设在 K线 i 收盘时入场，所以要在 K线 i+1 ... 检查退出
                # 这里为了简化，我们假设在 K线 i 信号出现后立即入场，
                # 然后在 K线 i+1 (next_k) 检查是否触发 SL/TP
                pass 
                
                # 逻辑修正：
                # 信号是在 K线 i 产生的。
                # 入场是在 K线 i 收盘价。
                # 盈亏是在 K线 i+1, i+2... 产生的。
                
                # 所以，如果当前有持仓，意味着是在之前的某个 k (entry_idx < i) 入场的
                # 我们检查当前 K 线 i 的 High/Low 是否触及 SL/TP
                
                if position == 'long':
                    if curr['low'] <= stop_loss:
                        exit_price = stop_loss # 穿仓按止损价算（略乐观，实盘可能有滑点）
                        exit_reason = "Stop Loss"
                    elif curr['high'] >= take_profit:
                        exit_price = take_profit
                        exit_reason = "Take Profit"
                    # 也可以加时间止损或均线回归止损
                        
                elif position == 'short':
                    if curr['high'] >= stop_loss:
                        exit_price = stop_loss
                        exit_reason = "Stop Loss"
                    elif curr['low'] <= take_profit:
                        exit_price = take_profit
                        exit_reason = "Take Profit"
                
                if exit_price:
                    # 计算盈亏
                    if position == 'long':
                        raw_pnl = (exit_price - entry_price) * size
                    else:
                        raw_pnl = (entry_price - exit_price) * size
                        
                    # 扣除手续费 (双边)
                    fee = (exit_price * size + entry_price * size) * COMMISSION_RATE
                    net_pnl = raw_pnl - fee
                    
                    self.balance += net_pnl
                    self.trades.append({
                        "entry_time": entry_time,
                        "exit_time": curr['timestamp'],
                        "type": position,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "size": size,
                        "pnl": net_pnl,
                        "reason": exit_reason,
                        "balance": self.balance
                    })
                    position = None
                    continue # 本根K线已平仓，不再开新仓
            
            # 2. 检查开仓信号 (无持仓时)
            if position is None:
                signal = detect_spike(curr)
                if signal:
                    atr = curr['atr']
                    
                    if signal == 'bullish':
                        # 做多
                        sl_dist = curr['low'] * 0.005 # 0.5% 硬止损
                        # 或者使用 ATR 止损: sl_dist = atr * 0.5
                        
                        stop_loss = curr['low'] - sl_dist
                        take_profit = curr['close'] + (atr * 2.0)
                        
                        # 风控仓位计算
                        risk_amt = self.balance * RISK_PER_TRADE
                        # 止损距离
                        price_dist = curr['close'] - stop_loss
                        if price_dist <= 0: continue
                        
                        size = risk_amt / price_dist
                        entry_price = curr['close']
                        position = 'long'
                        entry_time = curr['timestamp']
                        
                    elif signal == 'bearish':
                        # 做空
                        sl_dist = curr['high'] * 0.005
                        
                        stop_loss = curr['high'] + sl_dist
                        take_profit = curr['close'] - (atr * 2.0)
                        
                        risk_amt = self.balance * RISK_PER_TRADE
                        price_dist = stop_loss - curr['close']
                        if price_dist <= 0: continue
                        
                        size = risk_amt / price_dist
                        entry_price = curr['close']
                        position = 'short'
                        entry_time = curr['timestamp']

    def report(self):
        if not self.trades:
            return "无交易记录"
            
        df_trades = pd.DataFrame(self.trades)
        total_trades = len(df_trades)
        win_trades = len(df_trades[df_trades['pnl'] > 0])
        loss_trades = len(df_trades[df_trades['pnl'] <= 0])
        win_rate = (win_trades / total_trades) * 100
        
        total_pnl = df_trades['pnl'].sum()
        roi = (total_pnl / self.initial_capital) * 100
        
        avg_win = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if win_trades > 0 else 0
        avg_loss = abs(df_trades[df_trades['pnl'] <= 0]['pnl'].mean()) if loss_trades > 0 else 0
        pf_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        # 最大回撤
        df_trades['peak'] = df_trades['balance'].cummax()
        df_trades['dd'] = (df_trades['peak'] - df_trades['balance']) / df_trades['peak']
        max_dd = df_trades['dd'].max() * 100
        
        return (
            f"交易次数: {total_trades}\n"
            f"胜率: {win_rate:.2f}%\n"
            f"总收益: {total_pnl:.2f} U ({roi:.2f}%)\n"
            f"最大回撤: {max_dd:.2f}%\n"
            f"平均盈亏比: {pf_ratio:.2f}\n"
            f"期末资金: {self.balance:.2f} U"
        )

def main():
    provider = DataProvider()
    
    print(f"🚀 开始回测 | 初始资金: {INITIAL_CAPITAL} U | 风险: {RISK_PER_TRADE*100}%")
    print(f"📂 本地数据路径: {LOCAL_DATA_PATH}\n")
    
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            # 简单的过滤：本地只测 1h
            # if tf != '1h': continue 
            
            df = provider.load_data(symbol, tf)
            if df is None or df.empty:
                continue
                
            if len(df) < 200:
                print(f"⚠️  数据不足 {symbol} {tf}")
                continue
                
            engine = BacktestEngine()
            engine.run(df)
            
            print(f"--- {symbol} {tf} ---")
            print(engine.report())
            print("-" * 30 + "\n")

if __name__ == "__main__":
    main()

