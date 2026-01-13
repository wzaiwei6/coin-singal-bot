#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 指标计算模块
"""
import pandas as pd
import numpy as np


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    计算MACD指标
    
    Args:
        df: K线数据，必须包含 'close' 列
        fast: 快速EMA周期
        slow: 慢速EMA周期
        signal: 信号线周期
        
    Returns:
        pd.DataFrame: 添加了 dif, dea, macd_hist, hist_delta 列的数据
    """
    df = df.copy()
    close = df["close"]
    
    # 计算EMA
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    # 计算DIF（快线 - 慢线）
    df["dif"] = ema_fast - ema_slow
    
    # 计算DEA（DIF的信号线）
    df["dea"] = df["dif"].ewm(span=signal, adjust=False).mean()
    
    # 计算MACD柱（DIF - DEA）
    df["macd_hist"] = df["dif"] - df["dea"]
    
    # 计算MACD柱的变化（当前柱 - 前一根柱）
    df["hist_delta"] = df["macd_hist"].diff()
    
    return df


def get_macd_trend(df: pd.DataFrame, lookback: int = 3) -> dict:
    """
    分析MACD趋势
    
    Args:
        df: 包含MACD指标的数据
        lookback: 回溯周期数
        
    Returns:
        dict: 趋势分析结果
    """
    if len(df) < lookback:
        return {
            "hist_trend": "unknown",
            "dif_trend": "unknown",
            "dea_trend": "unknown",
            "momentum": 0.0
        }
    
    recent = df.iloc[-lookback:]
    
    # 分析MACD柱趋势
    hist_changes = recent["hist_delta"].dropna()
    if len(hist_changes) > 0:
        hist_up = (hist_changes > 0).sum()
        hist_down = (hist_changes < 0).sum()
        if hist_up > hist_down:
            hist_trend = "increasing"
        elif hist_down > hist_up:
            hist_trend = "decreasing"
        else:
            hist_trend = "flat"
    else:
        hist_trend = "unknown"
    
    # 分析DIF趋势
    dif_changes = recent["dif"].diff().dropna()
    if len(dif_changes) > 0:
        dif_trend = "increasing" if dif_changes.iloc[-1] > 0 else "decreasing"
    else:
        dif_trend = "unknown"
    
    # 分析DEA趋势
    dea_changes = recent["dea"].diff().dropna()
    if len(dea_changes) > 0:
        dea_trend = "increasing" if dea_changes.iloc[-1] > 0 else "decreasing"
    else:
        dea_trend = "unknown"
    
    # 计算动能强度（MACD柱的变化率）
    if len(recent) >= 2:
        momentum = float(recent["macd_hist"].iloc[-1] / (abs(recent["macd_hist"].iloc[-2]) + 1e-10))
    else:
        momentum = 0.0
    
    return {
        "hist_trend": hist_trend,
        "dif_trend": dif_trend,
        "dea_trend": dea_trend,
        "momentum": momentum,
        "hist_consecutive": check_consecutive_trend(recent["macd_hist"])
    }


def check_consecutive_trend(series: pd.Series) -> int:
    """
    检查连续的趋势方向
    
    Args:
        series: 时间序列数据
        
    Returns:
        int: 正数表示连续上升的根数，负数表示连续下降的根数
    """
    if len(series) < 2:
        return 0
    
    diffs = series.diff().dropna()
    if len(diffs) == 0:
        return 0
    
    # 从最后一根K线开始向前检查
    count = 0
    last_direction = None
    
    for diff in reversed(diffs.values):
        if np.isnan(diff) or diff == 0:
            break
        
        direction = 1 if diff > 0 else -1
        
        if last_direction is None:
            last_direction = direction
            count = 1
        elif direction == last_direction:
            count += 1
        else:
            break
    
    return count * last_direction if last_direction else 0
