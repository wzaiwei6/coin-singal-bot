#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模型定义
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Signal:
    """交易信号数据结构"""
    symbol: str                      # 交易对，如 "BTCUSDT"
    timeframe: str                   # 时间周期，如 "1h"
    direction: str                   # 方向: "BUY" 或 "SELL"
    price: float                     # 当前价格
    timestamp: datetime              # 信号生成时间
    
    confidence: float                # 置信度 (0~1)
    risk_level: str                  # 风险等级: "HIGH", "MID", "LOW"
    suggestion: str                  # 建议操作: "BUY", "SELL", "WATCH"
    
    reasons: List[str] = field(default_factory=list)  # 信号原因列表
    
    key_levels: Dict[str, any] = field(default_factory=dict)  # 关键价格位
    # key_levels 包含:
    # - support: List[float]  支撑位
    # - resistance: List[float]  阻力位
    # - invalid: float  失效位
    
    # 指标详情（用于LLM分析）
    macd_hist: Optional[float] = None
    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    atr_quantile: Optional[float] = None
    volume: Optional[float] = None
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "suggestion": self.suggestion,
            "reasons": self.reasons,
            "key_levels": self.key_levels,
            "macd_hist": self.macd_hist,
            "macd_dif": self.macd_dif,
            "macd_dea": self.macd_dea,
            "atr": self.atr,
            "atr_pct": self.atr_pct,
            "atr_quantile": self.atr_quantile,
            "volume": self.volume,
        }
