#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD + 波动率策略模块
"""
from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np

from models import Signal
from indicators.macd import calculate_macd, get_macd_trend, check_consecutive_trend
from indicators.volatility import calculate_atr, get_volatility_state, calculate_price_range


def generate_signal(df: pd.DataFrame, symbol: str, timeframe: str, config: dict) -> Optional[Signal]:
    """
    基于MACD动能变化 + 波动率状态生成交易信号
    
    Args:
        df: K线数据
        symbol: 交易对
        timeframe: 时间周期
        config: 策略配置
        
    Returns:
        Signal对象 或 None（无信号）
    """
    if len(df) < 50:
        return None
    
    # 获取策略参数
    macd_params = config.get("strategy", {}).get("macd", {})
    atr_params = config.get("strategy", {}).get("atr", {})
    
    fast = macd_params.get("fast", 12)
    slow = macd_params.get("slow", 26)
    signal = macd_params.get("signal", 9)
    atr_period = atr_params.get("period", 14)
    low_quantile = atr_params.get("low_quantile", 0.2)
    high_quantile = atr_params.get("high_quantile", 0.8)
    
    # 计算指标
    df = calculate_macd(df, fast, slow, signal)
    df = calculate_atr(df, atr_period)
    
    # 检查是否有足够的数据
    if len(df) < 3:
        return None
    
    # 获取最近的数据
    current = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]
    
    # 检查NaN值
    if pd.isna(current["macd_hist"]) or pd.isna(current["atr_quantile"]):
        return None
    
    # 获取MACD趋势分析
    macd_trend = get_macd_trend(df, lookback=3)
    
    # 获取波动率状态
    vol_state = get_volatility_state(df, low_quantile, high_quantile)
    
    # 获取价格范围
    price_range = calculate_price_range(df, lookback=20)
    
    # 判断信号方向
    direction = None
    reasons = []
    
    # === SELL 信号条件 ===
    # 1. MACD hist 连续下降 ≥ 2 根
    # 2. hist 当前 < 0 或明显回落
    # 3. atr_quantile ∈ [low_quantile, high_quantile] (过滤极端波动)
    
    hist_consecutive = check_consecutive_trend(df["macd_hist"].iloc[-3:])
    
    if hist_consecutive <= -2:  # 连续下降至少2根
        if current["macd_hist"] < 0 or current["hist_delta"] < 0:
            if low_quantile <= current["atr_quantile"] <= high_quantile:
                direction = "SELL"
                reasons.append(f"MACD动能连续下降{abs(hist_consecutive)}根,柱体转弱")
                
                if current["macd_hist"] < 0:
                    reasons.append("MACD柱体已转为负值,空头动能增强")
                
                if macd_trend["dif_trend"] == "decreasing" and macd_trend["dea_trend"] == "decreasing":
                    reasons.append("DIF和DEA同时向下,趋势一致性强")
    
    # === BUY 信号条件 ===
    # 1. MACD hist 连续上升 ≥ 2 根
    # 2. hist 当前 > 0 或明显抬升
    # 3. atr_quantile ∈ [low_quantile, high_quantile]
    
    elif hist_consecutive >= 2:  # 连续上升至少2根
        if current["macd_hist"] > 0 or current["hist_delta"] > 0:
            if low_quantile <= current["atr_quantile"] <= high_quantile:
                direction = "BUY"
                reasons.append(f"MACD动能连续上升{hist_consecutive}根,柱体走强")
                
                if current["macd_hist"] > 0:
                    reasons.append("MACD柱体已转为正值,多头动能增强")
                
                if macd_trend["dif_trend"] == "increasing" and macd_trend["dea_trend"] == "increasing":
                    reasons.append("DIF和DEA同时向上,趋势一致性强")
    
    # 如果没有满足条件的信号
    if direction is None:
        return None
    
    # === 计算置信度（多维度加权）===
    confidence = calculate_confidence(
        df, macd_trend, vol_state, price_range, direction
    )
    
    # === 计算风险等级 ===
    risk_level = calculate_risk_level(vol_state, price_range, direction)
    
    # === 生成操作建议 ===
    suggestion = generate_suggestion(confidence, risk_level, vol_state, direction)
    
    # === 添加波动率相关原因 ===
    if vol_state["state"] == "high":
        reasons.append(f"当前波动率处于高位({vol_state['atr_quantile']:.2f}),回撤风险增加")
    elif vol_state["state"] == "normal":
        reasons.append(f"波动率适中({vol_state['atr_quantile']:.2f}),市场状态健康")
    
    # === 计算关键价格位 ===
    key_levels = calculate_key_levels(df, direction, price_range)
    
    # 构建信号对象
    signal = Signal(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        price=float(current["close"]),
        timestamp=datetime.now(),
        confidence=confidence,
        risk_level=risk_level,
        suggestion=suggestion,
        reasons=reasons,
        key_levels=key_levels,
        macd_hist=float(current["macd_hist"]),
        macd_dif=float(current["dif"]),
        macd_dea=float(current["dea"]),
        atr=float(current["atr"]),
        atr_pct=float(current["atr_pct"]),
        atr_quantile=float(current["atr_quantile"]),
        volume=float(current["volume"])
    )
    
    return signal


def calculate_confidence(df: pd.DataFrame, macd_trend: dict, vol_state: dict, 
                        price_range: dict, direction: str) -> float:
    """
    计算信号置信度（0~1）
    
    多维度加权:
    1. MACD动能一致性 (30%)
    2. 波动率健康度 (30%)
    3. 价格距关键位距离 (20%)
    4. 成交量配合度 (20%)
    """
    score = 0.0
    
    # 1. MACD动能一致性 (30%)
    if macd_trend["hist_consecutive"]:
        # 连续根数越多,得分越高（最多5根）
        consecutive_score = min(abs(macd_trend["hist_consecutive"]) / 5.0, 1.0)
        
        # DIF和DEA方向一致性
        if direction == "SELL":
            if macd_trend["dif_trend"] == "decreasing" and macd_trend["dea_trend"] == "decreasing":
                consecutive_score *= 1.2
        else:  # BUY
            if macd_trend["dif_trend"] == "increasing" and macd_trend["dea_trend"] == "increasing":
                consecutive_score *= 1.2
        
        score += min(consecutive_score, 1.0) * 0.3
    
    # 2. 波动率健康度 (30%)
    if vol_state["suitable_for_entry"]:
        # 波动率在正常范围,得满分
        vol_score = 1.0
    else:
        # 波动率异常,降低分数
        atr_q = vol_state["atr_quantile"]
        if atr_q < 0.2:
            vol_score = atr_q / 0.2  # 0~0.2映射到0~1
        else:  # atr_q > 0.8
            vol_score = (1.0 - atr_q) / 0.2  # 0.8~1映射到1~0
    
    score += vol_score * 0.3
    
    # 3. 价格距关键位距离 (20%)
    position_pct = price_range["position_pct"]
    if direction == "SELL":
        # 做空时,价格越靠近高点越好
        position_score = position_pct
    else:  # BUY
        # 做多时,价格越靠近低点越好
        position_score = 1.0 - position_pct
    
    score += position_score * 0.2
    
    # 4. 成交量配合度 (20%)
    # 计算最近3根K线的成交量平均值与历史平均值的比率
    recent_volume = df["volume"].iloc[-3:].mean()
    avg_volume = df["volume"].iloc[-20:].mean()
    
    if avg_volume > 0:
        volume_ratio = recent_volume / avg_volume
        volume_score = min(volume_ratio / 1.5, 1.0)  # 1.5倍以上算满分
    else:
        volume_score = 0.5
    
    score += volume_score * 0.2
    
    return round(score, 2)


def calculate_risk_level(vol_state: dict, price_range: dict, direction: str) -> str:
    """
    计算风险等级
    
    Returns:
        "HIGH", "MID", "LOW"
    """
    atr_q = vol_state["atr_quantile"]
    
    # 基于波动率分位数
    if atr_q > 0.8:
        return "HIGH"
    elif atr_q < 0.3:
        return "LOW"
    else:
        return "MID"


def generate_suggestion(confidence: float, risk_level: str, vol_state: dict, direction: str) -> str:
    """
    生成操作建议
    
    Args:
        confidence: 置信度
        risk_level: 风险等级
        vol_state: 波动率状态
        direction: 信号方向 (BUY/SELL)
    
    Returns:
        "BUY", "SELL", "WATCH"
    """
    # 高风险时只观望
    if risk_level == "HIGH":
        return "WATCH"
    
    # 低置信度时观望
    if confidence < 0.4:
        return "WATCH"
    
    # 置信度较高且风险可控时，返回对应的操作建议
    if confidence >= 0.6 and risk_level in ["LOW", "MID"]:
        return direction  # 直接返回信号方向：BUY 或 SELL
    
    return "WATCH"


def calculate_key_levels(df: pd.DataFrame, direction: str, price_range: dict) -> dict:
    """
    计算关键价格位
    
    Returns:
        dict: 包含 support, resistance, invalid
    """
    recent = df.iloc[-20:]
    current_price = df.iloc[-1]["close"]
    
    # 计算支撑位（近期低点）
    support_levels = []
    lows = recent["low"].values
    for i in range(1, len(lows) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            support_levels.append(float(lows[i]))
    
    # 如果没有找到局部低点,使用最低价
    if not support_levels:
        support_levels = [float(recent["low"].min())]
    
    support_levels = sorted(support_levels)[-3:]  # 取最近的3个支撑位
    
    # 计算阻力位（近期高点）
    resistance_levels = []
    highs = recent["high"].values
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            resistance_levels.append(float(highs[i]))
    
    # 如果没有找到局部高点,使用最高价
    if not resistance_levels:
        resistance_levels = [float(recent["high"].max())]
    
    resistance_levels = sorted(resistance_levels, reverse=True)[:3]  # 取最近的3个阻力位
    
    # 计算失效位（突破后策略失效的价格）
    if direction == "SELL":
        # 做空时,价格突破最近的阻力位则失效（向上突破）
        # 失效位应该在当前价格上方
        invalid_price = resistance_levels[0] if resistance_levels else current_price * 1.05
    else:  # BUY
        # 做多时,价格跌破止损位则失效（向下跌破）
        # 失效位应该在当前价格下方
        # 使用最近的、在当前价格下方的支撑位
        valid_supports = [s for s in support_levels if s < current_price]
        if valid_supports:
            # 使用最近的下方支撑
            invalid_price = valid_supports[-1]  # 最高的下方支撑
        else:
            # 如果没有下方支撑，使用固定百分比
            invalid_price = current_price * 0.95  # 当前价格的95%
    
    return {
        "support": support_levels,
        "resistance": resistance_levels,
        "invalid": float(invalid_price)
    }
