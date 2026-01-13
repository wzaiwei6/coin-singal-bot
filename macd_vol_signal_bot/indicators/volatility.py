#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
波动率指标计算模块 - ATR (Average True Range)
"""
import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算ATR（平均真实波幅）及相关指标
    
    Args:
        df: K线数据，必须包含 'high', 'low', 'close' 列
        period: ATR周期
        
    Returns:
        pd.DataFrame: 添加了 atr, atr_pct, atr_quantile 列的数据
    """
    df = df.copy()
    
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    
    # 计算真实波幅 (True Range)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 计算ATR（TR的移动平均）
    df["atr"] = tr.rolling(period, min_periods=period).mean()
    
    # 计算ATR百分比（ATR / 收盘价）
    df["atr_pct"] = df["atr"] / close * 100
    
    # 计算ATR分位数（在最近N根K线中的位置）
    # 分位数范围：0~1，0.5表示中等波动
    df["atr_quantile"] = df["atr"].rolling(window=period * 3, min_periods=period).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5,
        raw=False
    )
    
    return df


def get_volatility_state(df: pd.DataFrame, low_threshold: float = 0.2, high_threshold: float = 0.8) -> dict:
    """
    分析波动率状态
    
    Args:
        df: 包含ATR指标的数据
        low_threshold: 低波动阈值
        high_threshold: 高波动阈值
        
    Returns:
        dict: 波动率状态分析
    """
    if len(df) == 0 or pd.isna(df.iloc[-1]["atr_quantile"]):
        return {
            "state": "unknown",
            "level": "unknown",
            "suitable_for_entry": False
        }
    
    current = df.iloc[-1]
    atr_q = current["atr_quantile"]
    
    # 判断波动率水平
    if atr_q < low_threshold:
        state = "low"
        level = "极低波动"
        suitable = False  # 波动太小，信号可能不可靠
    elif atr_q > high_threshold:
        state = "high"
        level = "极高波动"
        suitable = False  # 波动太大，风险过高
    else:
        state = "normal"
        level = "正常波动"
        suitable = True   # 波动适中，适合入场
    
    return {
        "state": state,
        "level": level,
        "suitable_for_entry": suitable,
        "atr_quantile": float(atr_q),
        "atr_value": float(current["atr"]),
        "atr_pct": float(current["atr_pct"])
    }


def calculate_price_range(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    计算价格波动范围
    
    Args:
        df: K线数据
        lookback: 回溯周期
        
    Returns:
        dict: 价格范围信息
    """
    if len(df) < lookback:
        lookback = len(df)
    
    recent = df.iloc[-lookback:]
    
    high_max = recent["high"].max()
    low_min = recent["low"].min()
    close_current = df.iloc[-1]["close"]
    
    # 计算当前价格在波动范围中的位置
    range_size = high_max - low_min
    if range_size > 0:
        position_pct = (close_current - low_min) / range_size
    else:
        position_pct = 0.5
    
    return {
        "high_max": float(high_max),
        "low_min": float(low_min),
        "range_size": float(range_size),
        "position_pct": float(position_pct),  # 0表示低点，1表示高点
        "close_current": float(close_current)
    }
