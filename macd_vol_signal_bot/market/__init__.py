"""市场数据模块 - 提供Binance行情数据接入"""
from market.binance import build_exchange, fetch_klines

__all__ = ["build_exchange", "fetch_klines"]
